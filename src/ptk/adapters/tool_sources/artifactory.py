"""Artifactory AQL lookup and HTTPS downloads through curl (no JFrog utility)."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit

from ...domain.config.model import ArtifactorySource, DownloadSource
from ...domain.errors import PtkError
from ...domain.execution.model import CommandSpec


def _url(base: str, *parts: str) -> str:
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise PtkError(
            "Artifactory requires an HTTPS base URL without credentials, query or fragment"
        )
    segments = []
    for part in parts:
        for segment in part.split("/"):
            if segment == ".":
                continue
            if not segment or segment == ".." or "\\" in segment:
                raise PtkError("Invalid Artifactory artifact path")
            segments.append(quote(segment, safe=""))
    return base.rstrip("/") + "/" + "/".join(segments)


class CurlArtifactory:
    def __init__(self, runner, environ, source: ArtifactorySource):
        self.runner = runner
        self.environ = dict(environ)
        self.source = source

    def fetch(self, url: str, destination: Path, *, query: str | None = None) -> None:
        executable = self.runner.which("curl", path=self.environ.get("PATH"))
        if not executable:
            raise PtkError("Artifactory installation requires curl on PATH")
        with tempfile.TemporaryDirectory(prefix="ptk-curl-") as tmp:
            config = Path(tmp) / "curl.conf"
            config.touch(mode=0o600)
            options = []
            if self.source.token_env:
                token = self.environ.get(self.source.token_env)
                if not token:
                    raise PtkError(
                        f"Missing Artifactory token environment variable: {self.source.token_env}"
                    )
                if any(ord(c) < 32 or ord(c) == 127 for c in token):
                    raise PtkError("Invalid Artifactory token")
                # curl config escaping; token is never part of argv, logs or markers.
                escaped = token.replace("\\", "\\\\").replace('"', '\\"')
                options.append(f'header = "Authorization: Bearer {escaped}"')
            config.write_text("\n".join(options), encoding="utf-8")
            argv = [
                executable,
                "--disable",
                "--config",
                str(config),
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--globoff",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--connect-timeout",
                "30",
                "--max-time",
                "600",
                "--retry",
                "2",
                "--output",
                str(destination),
            ]
            if query is not None:
                payload = Path(tmp) / "query.aql"
                payload.write_text(query, encoding="utf-8")
                argv += [
                    "--header",
                    "Content-Type: text/plain",
                    "--data-binary",
                    f"@{payload}",
                ]
            argv += ["--url", url]
            # Do not forward server/curl diagnostics that could echo credentials.
            outcome = self.runner.run(
                CommandSpec(argv=argv, env=self.environ, timeout=1800), lambda _: None
            )
            if outcome.exit_code != 0:
                raise PtkError(
                    f"Artifactory curl request failed (exit code {outcome.exit_code}); check credentials, URL and connectivity"
                )

    def resolve(self) -> DownloadSource:
        source = self.source
        lookup = bool(source.properties) or any(
            c in source.path + source.name for c in "*?"
        )
        digest = source.sha256
        path, name = source.path, source.name
        if lookup:
            criteria = {
                "repo": source.repository,
                "type": "file",
                "path": {"$match": path},
                "name": {"$match": name},
            }
            criteria.update({f"@{k}": {"$eq": v} for k, v in source.properties.items()})
            query = (
                "items.find(" + json.dumps(criteria) + ")"
                '.include("repo","path","name","sha256","created")'
                '.sort({"$desc":["created","repo","path","name"]}).limit(2)'
            )
            with tempfile.TemporaryDirectory(prefix="ptk-aql-") as tmp:
                result = Path(tmp) / "result.json"
                self.fetch(_url(source.url, "api/search/aql"), result, query=query)
                try:
                    rows = json.loads(result.read_text(encoding="utf-8"))["results"]
                    if not isinstance(rows, list):
                        raise TypeError
                    if not rows:
                        raise PtkError(
                            "No Artifactory artifact matches the configured selection"
                        )
                    if len(rows) > 1 and source.select == "unique":
                        raise PtkError(
                            "Multiple Artifactory artifacts match; pin the path/properties or use select: latest"
                        )
                    item = rows[0]
                    if item["repo"] != source.repository:
                        raise ValueError
                    path, name = item["path"], item["name"]
                    digest = digest or item.get("sha256")
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    raise PtkError("Invalid Artifactory AQL response") from exc
        if not isinstance(path, str) or not isinstance(name, str):
            raise PtkError("Invalid Artifactory artifact path")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise PtkError(
                "Artifactory requires sha256 in configuration or the AQL response"
            )
        return DownloadSource(
            url=_url(source.url, source.repository, path, name),
            sha256=digest,
            extract=source.extract,
            bin=source.bin,
        )
