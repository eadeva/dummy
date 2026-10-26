"""Short-lived loopback report links; only registered reports and logs are served.

This module also runs as a detached, standard-library-only helper so links remain
usable after the PTK command exits. No source tree or directory listing is served.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from html import escape, unescape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import ProxyHandler, build_opener, url2pathname


def read_state(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("invalid report viewer state")  # noqa: TRY004 - malformed persisted data
    return value


def write_state(path, data):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as file:
        temporary = Path(file.name)
        json.dump(data, file)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def alive(state):
    try:
        url = f"http://127.0.0.1:{int(state['port'])}/{state['token']}/health"
        with build_opener(ProxyHandler({})).open(url, timeout=0.5) as response:
            return response.read() == b"ptk-report-viewer"
    except (OSError, ValueError, KeyError):
        return False


def report_url(path: Path, root: Path, logs=(), *, idle_seconds=3600) -> str:
    from ..locking import file_lock

    path = path.resolve(strict=True)
    directory = root / ".ptk" / "report-viewer"
    directory.mkdir(parents=True, exist_ok=True)
    registry = directory / "server.json"
    with file_lock(directory / "server.lock"):
        try:
            state = read_state(registry)
        except (OSError, ValueError):
            state = {}
        if not isinstance(state.get("registrations"), dict):
            state = {}
        running = alive(state)
        if not running:
            state = {"token": secrets.token_urlsafe(24), "registrations": {}}
        key = hashlib.sha256(str(path.parent).encode()).hexdigest()[:20]
        state["registrations"][key] = {
            "root": str(path.parent),
            "logs": sorted({str(Path(log).resolve()) for log in logs if log}),
        }
        write_state(registry, state)
        if not running:
            ready = directory / f"{state['token']}.ready"
            options = (
                {
                    "creationflags": subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                }
                if os.name == "nt"
                else {"start_new_session": True}
            )
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve()),
                    "--state",
                    str(registry.resolve()),
                    "--token",
                    state["token"],
                    "--ready",
                    str(ready.resolve()),
                    "--idle",
                    str(idle_seconds),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                **options,
            )
            deadline = time.monotonic() + 5
            while (
                not ready.exists()
                and child.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            if not ready.exists():
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
                raise OSError("local report viewer did not start")
            state.update(read_state(ready))
            ready.unlink(missing_ok=True)
            write_state(registry, state)
        return f"http://127.0.0.1:{state['port']}/{state['token']}/r/{key}/{quote(path.name)}"


class ReportHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond(body=True)

    def do_HEAD(self):
        self.respond(body=False)

    def respond(self, *, body):
        expected = {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }
        if self.headers.get("Host") not in expected:
            self.send_error(403)
            return
        try:
            state = read_state(self.server.registry)
            parts = urlsplit(self.path).path.split("/", 4)
            if (
                state["token"] != self.server.token
                or len(parts) < 3
                or parts[1] != self.server.token
            ):
                self.send_error(404)
                return
            if parts[2:] == ["health"]:
                data, content_type = b"ptk-report-viewer", "text/plain"
            else:
                if len(parts) != 5 or parts[2] != "r":
                    self.send_error(404)
                    return
                entry = state["registrations"][parts[3]]
                root = Path(entry["root"]).resolve()
                path = (root / unquote(parts[4])).resolve()
                permitted = path.is_relative_to(root) or str(path) in entry["logs"]
                if not permitted or not path.is_file():
                    self.send_error(404)
                    return
                data = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
                if path.suffix.lower() == ".html":
                    data = rewrite_links(
                        data, path, root, f"/{self.server.token}/r/{parts[3]}/"
                    )
        except (OSError, ValueError, KeyError):
            self.send_error(404)
            return
        self.server.last_request = time.monotonic()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if body:
            self.wfile.write(data)


def rewrite_links(data, path, root, prefix):
    """Keep nested reports and relative log links valid without URL traversal."""

    class Rewriter(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.output = []

        def handle_starttag(self, tag, attrs):
            def replace(match):
                href = unescape(match[3])
                parsed = urlsplit(href)
                if (
                    parsed.scheme not in ("", "file")
                    or (parsed.netloc and parsed.scheme != "file")
                    or not parsed.path
                ):
                    return match[0]
                target = (
                    Path(url2pathname(parsed.path))
                    if parsed.scheme == "file"
                    else path.parent / unquote(parsed.path)
                )
                url = prefix + quote(str(target.resolve()), safe="")
                if parsed.fragment:
                    url += "#" + parsed.fragment
                return match[1] + match[2] + escape(url, quote=True) + match[2]

            self.output.append(
                re.sub(
                    r"""(\bhref\s*=\s*)(["'])(.*?)\2""",
                    replace,
                    self.get_starttag_text(),
                    flags=re.IGNORECASE,
                )
            )

        handle_startendtag = handle_starttag

        def handle_endtag(self, tag):
            self.output.append(f"</{tag}>")

        def handle_data(self, data):
            self.output.append(data)

        def handle_entityref(self, name):
            self.output.append(f"&{name};")

        def handle_charref(self, name):
            self.output.append(f"&#{name};")

        def handle_comment(self, data):
            self.output.append(f"<!--{data}-->")

        def handle_decl(self, decl):
            self.output.append(f"<!{decl}>")

    parser = Rewriter()
    parser.feed(data.decode("utf-8"))
    parser.close()
    return "".join(parser.output).encode("utf-8")


def serve(registry, token, ready, idle_seconds):
    with HTTPServer(("127.0.0.1", 0), ReportHandler) as server:
        server.registry, server.token = registry, token
        server.last_request = time.monotonic()
        server.timeout = 0.5
        write_state(ready, {"port": server.server_port, "pid": os.getpid()})
        while time.monotonic() - server.last_request < idle_seconds:
            try:
                if read_state(registry).get("token") != token:
                    break
            except (OSError, ValueError):
                break
            server.handle_request()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--idle", type=float, default=3600)
    args = parser.parse_args()
    serve(args.state, args.token, args.ready, args.idle)
