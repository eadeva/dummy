"""Real loopback links survive CLI exit without exposing unrelated files."""

import io
import re
import time
from html import unescape
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

import pytest
from rich.console import Console

from ptk.adapters.reporting.viewer import alive, read_state, report_url
from ptk.drivers.cli import report_links


@pytest.fixture
def viewer(tmp_path):
    def register(path, logs=(), **kwargs):
        return report_url(path, tmp_path, logs, **kwargs)

    yield register
    registry = tmp_path / ".ptk/report-viewer/server.json"
    registry.unlink(missing_ok=True)


def request(url, **kwargs):
    return build_opener(ProxyHandler({})).open(Request(url, **kwargs), timeout=3)


def test_token_starting_with_hyphen_is_not_parsed_as_an_option(
    tmp_path, viewer, monkeypatch
):
    monkeypatch.setattr(
        "ptk.adapters.reporting.viewer.secrets.token_urlsafe",
        lambda size: "-leading-hyphen",
    )
    path = tmp_path / "report.html"
    path.write_text("<html>ok</html>", encoding="utf-8")
    url = viewer(path)
    assert "/-leading-hyphen/" in url
    with request(url) as response:
        assert response.read() == b"<html>ok</html>"


def test_links_serve_html_children_and_logs_but_not_source(tmp_path, viewer):
    root = tmp_path / "reports with spaces"
    child = root / "children"
    child.mkdir(parents=True)
    log = tmp_path / "run log ü.txt"
    log.write_text("a log", encoding="utf-8")
    secret = tmp_path / "unrelated.txt"
    secret.write_text("not a report", encoding="utf-8")
    (root / "report.html").write_text(
        '<html><a href="children/test.html">child</a></html>', encoding="utf-8"
    )
    (child / "test.html").write_text(
        '<html><a href="../../run%20log%20%C3%BC.txt">log</a></html>', encoding="utf-8"
    )
    url = viewer(root / "report.html", [log])
    with request(url) as response:
        html = response.read().decode()
    child_url = urljoin(url, unescape(re.search('href="([^"]+)"', html)[1]))
    with request(child_url) as response:
        child_html = response.read().decode()
    log_url = urljoin(url, unescape(re.search('href="([^"]+)"', child_html)[1]))
    with request(log_url) as response:
        assert response.read() == b"a log"
    prefix = url.rsplit("/", 1)[0] + "/"
    for forbidden in (
        prefix + quote(str(secret), safe=""),
        prefix,
        url.replace(urlsplit(url).path.split("/")[1], "wrong-token"),
    ):
        with pytest.raises(HTTPError) as exc:
            request(forbidden)
        assert exc.value.code == 404
    with pytest.raises(HTTPError) as exc:
        request(url, headers={"Host": "example.invalid"})
    assert exc.value.code == 403


def test_reuses_server_and_expires_when_idle(tmp_path, viewer):
    paths = []
    for name in ("one", "two"):
        folder = tmp_path / name
        folder.mkdir()
        path = folder / "report.html"
        path.write_text("<html>ok</html>", encoding="utf-8")
        paths.append(path)
    first = viewer(paths[0], idle_seconds=1)
    second = viewer(paths[1], idle_seconds=1)
    assert urlsplit(first).netloc == urlsplit(second).netloc
    state = read_state(tmp_path / ".ptk/report-viewer/server.json")
    assert len(state["registrations"]) == 2
    time.sleep(1.7)
    assert not alive(state)


@pytest.mark.parametrize(
    "ci,terminal,vscode,expected",
    [
        (False, True, True, True),
        (True, True, True, False),
        (False, False, True, False),
        (False, True, False, False),
    ],
)
def test_console_links_only_in_interactive_local_vscode(
    tmp_path, monkeypatch, ci, terminal, vscode, expected
):
    output = io.StringIO()
    monkeypatch.setattr(
        report_links, "console", Console(file=output, force_terminal=terminal)
    )
    called = []

    def link(path, **kwargs):
        called.append(path)
        return "http://127.0.0.1:1234/report.html"

    app = SimpleNamespace(
        host=SimpleNamespace(
            variables={"TERM_PROGRAM": "vscode" if vscode else "other"}
        ),
        report_url=link,
    )
    report_links.print_report(app, tmp_path / "report.html", root=tmp_path, ci=ci)
    assert bool(called) == expected
    assert ("browser: http://127.0.0.1" in output.getvalue()) == expected


def test_viewer_failure_does_not_fail_the_command(tmp_path, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(
        report_links, "console", Console(file=output, force_terminal=True)
    )

    def fail(*args, **kwargs):
        raise OSError("cannot bind")

    app = SimpleNamespace(
        host=SimpleNamespace(variables={"TERM_PROGRAM": "vscode"}), report_url=fail
    )
    report_links.print_report(app, tmp_path / "report.html", root=tmp_path)
    assert "browser link unavailable" in output.getvalue()
