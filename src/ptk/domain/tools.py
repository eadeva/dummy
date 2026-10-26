"""Tool requirements (pure): version checks and the order of install methods.

    tools:
      cmake:
        version: ">=3.28,<4"
        check: cmake --version
        choco: {package: cmake, version: "3.30.2"}   # Windows
        uv_tool: cmake==3.30.2                       # Windows + Linux
        download: {linux: {url: ..., sha256: ..., bin: bin}}
        apt: cmake                                   # only with --allow-system

Install order: Windows choco -> uv tool -> download; Linux/macOS uv tool ->
download -> apt/dnf (only when system package managers are allowed).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .config.model import ChocoSource, DownloadSource, ToolSpec


@dataclass
class ToolStatus:
    name: str
    required: str | None  # version range
    found: bool
    version: str | None = None
    problem: str = ""
    source: str = ""  # Resolved check executable in the selected command environment.

    @property
    def ok(self) -> bool:
        return self.found and not self.problem


@dataclass(frozen=True)
class InstallMethod:
    kind: str  # choco | uv_tool | download | apt | dnf
    package: str  # package / requirement / url
    version: str | None = None
    download: DownloadSource | None = None
    options: dict[str, Any] = field(default_factory=dict)
    identity: str = ""

    def describe(self) -> str:
        if self.kind.startswith("plugin:"):
            return f"{self.kind} ({self.package})"
        if self.kind in {"toolbase", "artifactory"}:
            return f"{self.kind} {self.package}"
        if self.kind == "choco":
            return f"choco install {self.package}" + (
                f" --version {self.version}" if self.version else ""
            )
        if self.kind == "uv_tool":
            return f"isolated Python tool {self.package}"
        if self.kind == "download":
            return f"download {self.package}"
        return f"sudo {self.kind} install {self.package}"


def parse_version(output: str, pattern: str) -> str | None:
    match = re.search(pattern, output)
    if not match:
        return None
    return match.group(1) if match.groups() else match.group(0)


def check_version(name: str, spec: ToolSpec, output: str | None) -> ToolStatus:
    """``output``: what the check command printed (None: not found / failed)."""
    if output is None:
        return ToolStatus(name, spec.version, found=False, problem="not found")
    version = parse_version(output, spec.version_regex)
    status = ToolStatus(name, spec.version, found=True, version=version)
    if spec.version:
        if version is None:
            status.problem = f"cannot read the version from '{spec.check}'"
        elif not satisfies(version, spec.version):
            status.problem = f"version {version} does not match {spec.version}"
    return status


def satisfies(version: str, required: str) -> bool:
    try:
        return SpecifierSet(required).contains(Version(version), prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return False


def install_methods(
    spec: ToolSpec, os_name: str, *, allow_system: bool
) -> list[InstallMethod]:
    methods: list[InstallMethod] = [
        InstallMethod(f"plugin:{name}", name, options=options)
        for name, options in spec.installers.items()
    ]
    if spec.toolbase is not None and os_name == "windows":
        source = spec.toolbase
        methods.append(
            InstallMethod(
                "toolbase", source.package, source.version, options=source.model_dump()
            )
        )
    artifact = spec.artifactory
    if isinstance(artifact, dict):
        artifact = artifact.get(os_name)
    if artifact is not None:
        methods.append(
            InstallMethod("artifactory", artifact.name, options=artifact.model_dump())
        )
    choco = spec.choco
    if os_name == "windows" and choco is not None:
        source = choco if isinstance(choco, ChocoSource) else ChocoSource(package=choco)
        methods.append(InstallMethod("choco", source.package, source.version))
    if spec.uv_tool:
        methods.append(InstallMethod("uv_tool", spec.uv_tool))
    download = spec.download
    if isinstance(download, dict):
        download = download.get("windows" if os_name == "windows" else "linux")
    if download is not None:
        methods.append(InstallMethod("download", download.url, download=download))
    if os_name != "windows" and allow_system:
        if spec.apt:
            methods.append(InstallMethod("apt", spec.apt))
        if spec.dnf:
            methods.append(InstallMethod("dnf", spec.dnf))
    return [replace(method, identity=tool_identity(spec)) for method in methods]


def tool_applies(spec: ToolSpec, os_name: str) -> bool:
    """A Toolbase-only definition is inactive outside Windows."""
    if os_name == "windows" or spec.toolbase is None:
        return True
    return bool(install_methods(spec, os_name, allow_system=True))


def check_command(name: str, spec: ToolSpec) -> str:
    return spec.check or f"{name} --version"


def tool_identity(spec: ToolSpec) -> str:
    """Stable identity for an effective tool definition (versions and sources)."""
    data = spec.model_dump(mode="json", exclude={"description"})
    # Keep identities of existing configurations stable when adding optional sources.
    for key in ("toolbase", "artifactory"):
        if data.get(key) is None:
            data.pop(key, None)
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:20]
