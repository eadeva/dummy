"""Version discovery configuration and pure resolved-value projections."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PtkError


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionSource(Strict):
    source: Literal["literal", "git", "file", "env", "command", "inherit"] = "inherit"
    version: str | None = None
    match: str = "v*"
    strip_prefix: str = ""
    first_parent: bool = True
    dirty: Literal["suffix", "ignore", "error"] = "suffix"
    allow_shallow: bool = False
    path: str | None = None
    format: Literal["text", "json", "toml", "yaml"] = "text"
    key: str | None = None
    regex: str | None = None
    variable: str | None = None
    command: list[str] | None = None
    timeout: float = Field(default=30, gt=0)
    fallback: VersionSource | None = None

    @model_validator(mode="after")
    def required(self):
        required = {
            "literal": self.version,
            "file": self.path,
            "env": self.variable,
            "command": self.command,
        }
        if self.source in required and not required[self.source]:
            raise ValueError(
                f"{self.source} version source requires its value/path/variable/command"
            )
        if self.regex:
            try:
                re.compile(self.regex)
            except re.error as exc:
                raise ValueError(f"invalid version regex: {exc}") from None
        return self


class VersionOverride(Strict):
    project: VersionSource | None = None
    components: dict[str, VersionSource] = Field(default_factory=dict)


class VersionDependency(Strict):
    variant: str | None = None


class VersioningSpec(VersionOverride):
    variants: dict[str, VersionOverride] = Field(default_factory=dict)
    dependencies: dict[str, VersionDependency] = Field(default_factory=dict)


def identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
        raise PtkError(f"invalid version identifier: {name!r}")
    return name.upper().replace("-", "_")


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


def resolved(value: str, *, raw: str, source: str, **metadata) -> dict:
    if not value or any(ord(c) < 32 for c in value):
        raise PtkError("discovered version must be a nonempty single-line value")
    result = {"value": value, "raw": raw, "source": source, **metadata}
    match = SEMVER.fullmatch(value)
    if match:
        major, minor, patch, pre, build = match.groups()
        if any(
            not part for suffix in (pre, build) if suffix for part in suffix.split(".")
        ) or any(
            part.isdigit() and len(part) > 1 and part.startswith("0")
            for part in (pre or "").split(".")
        ):
            return result
        result.update(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=pre or "",
            build_metadata=build or "",
        )
    return result


def variables(snapshot: dict, *, provenance: bool = True) -> dict[str, str | int]:
    result = {}

    def add(prefix, item):
        fields = {"": item["value"]}
        for name in ("major", "minor", "patch", "prerelease", "build_metadata"):
            if name in item:
                fields["_" + name.upper()] = item[name]
        if provenance:
            fields["_RAW"] = item["raw"]
            for name in ("commit", "distance", "dirty", "tag"):
                if name in item.get("git", {}):
                    v = item["git"][name]
                    fields["_GIT_" + name.upper()] = (
                        str(v).lower() if isinstance(v, bool) else v
                    )
        for suffix, value in fields.items():
            key = prefix + suffix
            if key in result:
                raise PtkError(f"version variable naming collision: {key}")
            result[key] = value

    for alias, project in snapshot.get("projects", {}).items():
        prefix = "PTK_VERSION_" + identifier(alias)
        add(prefix, project)
        for name, component in project["components"].items():
            add(prefix + "_COMPONENT_" + identifier(name), component)
    return result
