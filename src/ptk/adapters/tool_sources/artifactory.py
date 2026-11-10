"""Artifactory AQL lookup and HTTPS downloads through curl (no JFrog utility)."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from ...domain.config.model import ArtifactorySource, DownloadSource
from ...domain.errors import PtkError
from ...domain.execution.model import CommandSpec


def _mib(size: int) -> str:
    return f"{size / (1024 * 1024):.0f} MiB"


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


@dataclass(frozen=True)
class Volume:
    url: str
    sha256: str
    size: int | None = None


class CurlArtifactory:
    def __init__(
        self, runner, environ, source: ArtifactorySource, token: str | None = None
    ):
        self.runner = runner
        self.environ = dict(environ)
        self.source = source
        self.token = token

    def _token(self) -> str | None:
        if self.token is not None:
            return self.token
        if not self.source.token_env:
            return None
        token = self.environ.get(self.source.token_env)
        if not token:
            raise PtkError(
                f"Missing Artifactory token environment variable: {self.source.token_env}"
            )
        return token

    def fetch(self, url: str, destination: Path, *, query: str | None = None) -> None:
        executable = self.runner.which("curl", path=self.environ.get("PATH"))
        if not executable:
            raise PtkError("Artifactory installation requires curl on PATH")
        with tempfile.TemporaryDirectory(prefix="ptk-curl-") as tmp:
            config = Path(tmp) / "curl.conf"
            config.touch(mode=0o600)
            options = []
            token = self._token()
            if token is not None:
                if not token or any(ord(c) < 32 or ord(c) == 127 for c in token):
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
            if outcome.exit_code == 22:
                raise PtkError(
                    "Artifactory rejected the request with an HTTP error (e.g. 401/403/404); check the token and access to the configured repository/path"
                )
            if outcome.exit_code != 0:
                raise PtkError(
                    f"Artifactory curl request failed (exit code {outcome.exit_code}); check credentials, URL and connectivity"
                )

    def resolve(self) -> DownloadSource:
        source = self.source
        lookup = (
            bool(source.properties)
            or any(c in source.path + source.name for c in "*?")
            or not source.sha256
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

    def volumes(self) -> list[Volume]:
        """The ordered volumes name.001, name.002, ... of a split archive (one folder)."""
        source = self.source
        criteria = {
            "repo": source.repository,
            "type": "file",
            "path": {"$match": source.path},
            "name": {"$match": f"{source.name}.*"},
        }
        criteria.update({f"@{k}": {"$eq": v} for k, v in source.properties.items()})
        query = (
            "items.find(" + json.dumps(criteria) + ")"
            '.include("repo","path","name","sha256","size")'
        )
        with tempfile.TemporaryDirectory(prefix="ptk-aql-") as tmp:
            result = Path(tmp) / "result.json"
            self.fetch(_url(source.url, "api/search/aql"), result, query=query)
            try:
                rows = json.loads(result.read_text(encoding="utf-8"))["results"]
                if not isinstance(rows, list):
                    raise TypeError
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise PtkError("Invalid Artifactory AQL response") from exc
        pattern = re.compile(re.escape(source.name) + r"\.(\d{3,})")
        numbered = {}
        for row in rows:
            match = pattern.fullmatch(str(row.get("name", "")))
            if match and row.get("repo") == source.repository:
                numbered[int(match.group(1))] = row
        if not numbered:
            raise PtkError("No Artifactory volumes match the configured split archive")
        if len({row["path"] for row in numbered.values()}) > 1:
            raise PtkError("Split archive volumes are in several folders; pin the path")
        if sorted(numbered) != list(range(1, len(numbered) + 1)):
            raise PtkError(
                "Split archive volumes are not numbered consecutively from .001"
            )
        volumes = []
        for number in sorted(numbered):
            row = numbered[number]
            digest = row.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(
                r"[a-fA-F0-9]{64}", digest
            ):
                raise PtkError(f"Artifactory reports no sha256 for {row['name']}")
            size = row.get("size")
            volumes.append(
                Volume(
                    _url(source.url, source.repository, row["path"], row["name"]),
                    digest,
                    size if isinstance(size, int) else None,
                )
            )
        return volumes

    def fetch_volumes(
        self,
        volumes: list[Volume],
        destination: Path,
        out: Callable[[str], None] = lambda _line: None,
    ) -> None:
        """Download and verify each volume, appending it to ``destination``."""
        total = sum(v.size or 0 for v in volumes)
        done = 0
        with (
            tempfile.TemporaryDirectory(prefix="ptk-volume-") as tmp,
            destination.open("wb") as joined,
        ):
            part = Path(tmp) / "volume"
            for number, volume in enumerate(volumes, 1):
                name = volume.url.rsplit("/", 1)[-1]
                size = f" ({_mib(volume.size)})" if volume.size else ""
                out(f"downloading volume {number}/{len(volumes)}: {name}{size}")
                self.fetch(volume.url, part)
                done += volume.size or 0
                if total:
                    out(f"  {_mib(done)} of {_mib(total)} downloaded")
                with part.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                if digest.lower() != volume.sha256.lower():
                    raise PtkError(f"sha256 mismatch for {volume.url}: got {digest}")
                with part.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        joined.write(chunk)
