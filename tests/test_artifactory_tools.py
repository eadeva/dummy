"""Artifactory transport, selection and managed installation without a live server."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from ptk.adapters.tool_sources.artifactory import CurlArtifactory
from ptk.adapters.tools import MARKER, SystemToolInstaller
from ptk.application.ports import ProcessOutcome
from ptk.domain.config.model import ArtifactorySource, ToolSpec
from ptk.domain.errors import PtkError
from ptk.domain.tools import install_methods


class CurlRunner:
    def __init__(self, payload=b"payload", rows=None, code=0):
        self.payload = payload
        self.rows = rows
        self.code = code
        self.calls = []
        self.configs = []
        self.queries = []

    def which(self, program, path=None):
        return "curl"

    def run(self, command, on_output, cancel=None):
        argv = command.argv
        self.calls.append(argv)
        self.configs.append(Path(argv[argv.index("--config") + 1]).read_text())
        if "--data-binary" in argv:
            self.queries.append(
                Path(argv[argv.index("--data-binary") + 1][1:]).read_text()
            )
            payload = json.dumps({"results": self.rows}).encode()
        else:
            payload = self.payload
        Path(argv[argv.index("--output") + 1]).write_bytes(payload)
        return ProcessOutcome(self.code)


def source(**kwargs):
    return ArtifactorySource(
        url="https://example.org/artifactory",
        repository="tools",
        **{"name": "tool.zip", **kwargs},
    )


def test_curl_install_and_cache(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("tool/bin/tool", "executable")
    runner = CurlRunner(buffer.getvalue())
    digest = hashlib.sha256(buffer.getvalue()).hexdigest()
    spec = ToolSpec(artifactory=source(sha256=digest, bin="bin", token_env="TOKEN"))
    installer = SystemToolInstaller(
        runner, {"TOKEN": 'secret"value'}, tools_dir=tmp_path
    )
    method = install_methods(spec, "linux", allow_system=False)[0]
    installer.install("tool", method, lambda _: None)
    installer.install("tool", method, lambda _: None)
    assert len(runner.calls) == 1
    assert "secret" not in str(runner.calls)
    assert 'Authorization: Bearer secret\\"value' in runner.configs[0]
    assert not Path(runner.calls[0][runner.calls[0].index("--config") + 1]).exists()
    [binary] = installer.bin_dirs({"tool": spec})
    assert (Path(binary) / "tool").read_text() == "executable"
    marker = next(tmp_path.rglob(MARKER)).read_text()
    assert digest in marker and "secret" not in marker


def test_aql_unique_and_latest():
    rows = [
        {
            "repo": "tools",
            "path": "compiler/1.2",
            "name": "tool.zip",
            "sha256": "a" * 64,
        }
    ]
    runner = CurlRunner(rows=rows)
    client = CurlArtifactory(runner, {}, source(properties={"version": "1.2"}))
    resolved = client.resolve()
    assert resolved.url.endswith("/tools/compiler/1.2/tool.zip")
    assert resolved.sha256 == "a" * 64
    assert '"@version": {"$eq": "1.2"}' in runner.queries[0]
    runner.rows = rows * 2
    with pytest.raises(PtkError, match="Multiple"):
        client.resolve()
    client.source = source(properties={"version": "1.2"}, select="latest")
    assert client.resolve() == resolved
    runner.rows = []
    with pytest.raises(PtkError, match="No Artifactory"):
        client.resolve()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org/?token=secret",
    ],
)
def test_reject_invalid_base_url(url):
    spec = source(sha256="a" * 64).model_copy(update={"url": url})
    with pytest.raises(PtkError, match="HTTPS"):
        CurlArtifactory(CurlRunner(), {}, spec).resolve()


def test_failure_does_not_install(tmp_path):
    for runner, digest in [(CurlRunner(code=22), "a" * 64), (CurlRunner(), "b" * 64)]:
        spec = ToolSpec(artifactory=source(sha256=digest))
        installer = SystemToolInstaller(runner, {}, tools_dir=tmp_path)
        method = install_methods(spec, "linux", allow_system=False)[0]
        with pytest.raises(PtkError):
            installer.install("tool", method, lambda _: None)
        assert not list(tmp_path.rglob(MARKER))


def test_missing_token_and_checksum(tmp_path):
    runner = CurlRunner()
    with pytest.raises(PtkError, match="sha256"):
        CurlArtifactory(runner, {}, source()).resolve()
    client = CurlArtifactory(runner, {}, source(token_env="TOKEN", sha256="a" * 64))
    with pytest.raises(PtkError, match="Missing Artifactory token"):
        client.fetch(client.resolve().url, tmp_path / "out")
    assert runner.calls == []


def test_os_source_selection():
    spec = ToolSpec(artifactory={"linux": source(sha256="a" * 64)})
    assert install_methods(spec, "windows", allow_system=False) == []
    assert install_methods(spec, "linux", allow_system=False)[0].kind == "artifactory"


class VolumeRunner(CurlRunner):
    """Serves AQL rows and the bytes of each volume by URL."""

    def __init__(self, volumes, rows):
        super().__init__(rows=rows)
        self.volumes = volumes

    def run(self, command, on_output, cancel=None):
        argv = command.argv
        if "--data-binary" in argv:
            return super().run(command, on_output, cancel)
        self.calls.append(argv)
        self.configs.append(Path(argv[argv.index("--config") + 1]).read_text())
        name = argv[argv.index("--url") + 1].rsplit("/", 1)[-1]
        Path(argv[argv.index("--output") + 1]).write_bytes(self.volumes[name])
        return ProcessOutcome(0)


def split_archive(parts=3):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("helix/common/bin/qagui", "gui")
    data = buffer.getvalue()
    size = -(-len(data) // parts)
    volumes = {
        f"helix.{i + 1:03d}": data[i * size : (i + 1) * size] for i in range(parts)
    }
    rows = [
        {"repo": "tools", "path": "Zipped/helix", "name": name,
         "sha256": hashlib.sha256(chunk).hexdigest()}
        for name, chunk in reversed(volumes.items())
    ] + [{"repo": "tools", "path": "Zipped/helix", "name": "helix.manifest", "sha256": "a" * 64}]  # fmt: skip
    return volumes, rows


def test_split_volumes_are_verified_joined_and_extracted(tmp_path):
    volumes, rows = split_archive()
    runner = VolumeRunner(volumes, rows)
    spec = ToolSpec(
        artifactory=source(
            name="helix", path="Zipped/helix", split=True, token="artifactory.token",
            bin="common/bin",
        )
    )  # fmt: skip
    installer = SystemToolInstaller(runner, {}, tools_dir=tmp_path)
    method = install_methods(spec, "linux", allow_system=False)[0]
    resolved = []
    lines = []
    installer.install(
        "helix", method, lines.append, secrets=lambda ref: resolved.append(ref) or "tok"
    )
    assert resolved == ["artifactory.token"]
    assert '"name": {"$match": "helix.*"}' in runner.queries[0]
    downloaded = [c[c.index("--url") + 1].rsplit("/", 1)[-1] for c in runner.calls[1:]]
    assert downloaded == ["helix.001", "helix.002", "helix.003"]
    assert all("Authorization: Bearer tok" in config for config in runner.configs)
    assert not any("warning" in line for line in lines)
    [binary] = installer.bin_dirs({"helix": spec})
    assert (Path(binary) / "qagui").read_text() == "gui"


def test_split_volume_checks(tmp_path):
    volumes, rows = split_archive()
    tampered = [
        {**row, "sha256": "b" * 64} if row["name"] == "helix.002" else row
        for row in rows
    ]
    spec = source(name="helix", split=True)
    client = CurlArtifactory(VolumeRunner(volumes, tampered), {}, spec)
    with pytest.raises(PtkError, match="sha256 mismatch"):
        client.fetch_volumes(client.volumes(), tmp_path / "joined")
    gap = [row for row in rows if row["name"] != "helix.002"]
    with pytest.raises(PtkError, match="consecutively"):
        CurlArtifactory(VolumeRunner(volumes, gap), {}, spec).volumes()
    with pytest.raises(PtkError, match="No Artifactory volumes"):
        CurlArtifactory(VolumeRunner(volumes, []), {}, spec).volumes()
    with pytest.raises(ValueError, match="literal base name"):
        source(name="helix*", split=True)
    with pytest.raises(ValueError, match="either token or token_env"):
        source(token="a.b", token_env="X")


def test_credential_tokens_need_a_resolver(tmp_path):
    spec = ToolSpec(artifactory=source(sha256="a" * 64, token="artifactory.token"))
    installer = SystemToolInstaller(CurlRunner(), {}, tools_dir=tmp_path)
    with pytest.raises(PtkError, match="cannot be resolved"):
        installer.install(
            "tool", install_methods(spec, "linux", allow_system=False)[0], print
        )


def test_new_optional_sources_preserve_existing_tool_identity():
    from ptk.domain.tools import tool_identity

    spec = ToolSpec(uv_tool="cmake==3.30.2")
    data = spec.model_dump(
        mode="json", exclude={"description", "toolbase", "artifactory", "docker"}
    )
    previous = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[
        :20
    ]
    assert tool_identity(spec) == previous


def test_archive_traversal_rejected(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escaped", "bad")
    payload = buffer.getvalue()
    spec = ToolSpec(artifactory=source(sha256=hashlib.sha256(payload).hexdigest()))
    installer = SystemToolInstaller(CurlRunner(payload), {}, tools_dir=tmp_path)
    with pytest.raises(PtkError, match="unsafe path"):
        installer.install(
            "tool",
            install_methods(spec, "linux", allow_system=False)[0],
            lambda _: None,
        )
    assert not list(tmp_path.rglob(MARKER))
