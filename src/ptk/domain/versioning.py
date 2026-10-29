"""Version discovery configuration and pure resolved-value projections."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PtkError


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionSource(Strict):
    source: Literal["literal", "git", "file", "env", "command", "inherit"] = Field(
        default="inherit",
        description="How to obtain the version: literal, git, file, env, command, or inherit from the containing context.",
    )
    version: str | None = Field(
        default=None, description="Fixed version string. Required for a literal source."
    )
    match: str = Field(
        default="v*",
        description="Git tag pattern used for version discovery, for example v*.",
    )
    strip_prefix: str = Field(
        default="",
        description="Prefix removed from the discovered version, for example v.",
    )
    first_parent: bool = Field(
        default=True,
        description="Follow only the first-parent Git history when locating a version tag.",
    )
    dirty: Literal["suffix", "ignore", "error"] = Field(
        default="suffix",
        description="How uncommitted changes affect a Git-derived version: add a suffix, ignore them, or fail.",
    )
    allow_shallow: bool = Field(
        default=False,
        description="Allow version discovery from a shallow Git checkout.",
    )
    path: str | None = Field(
        default=None,
        description="File containing the version. Required for a file source.",
    )
    format: Literal["text", "json", "toml", "yaml"] = Field(
        default="text",
        description="Format of the version file: plain text, JSON, TOML or YAML.",
    )
    key: str | None = Field(
        default=None,
        description="Key used to select the version from structured file content.",
    )
    regex: str | None = Field(
        default=None,
        description="Regular expression used to extract the version from the source value.",
    )
    variable: str | None = Field(
        default=None,
        description="Environment variable containing the version. Required for an env source.",
    )
    command: list[str] | None = Field(
        default=None,
        description="Command and arguments that print a version. Required for a command source.",
    )
    timeout: float = Field(
        description="Maximum time in seconds allowed for the version command.",
        default=30,
        gt=0,
    )
    fallback: VersionSource | None = Field(
        default=None,
        description="Alternative version source used if this source cannot provide a version.",
    )

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
    project: VersionSource | None = Field(
        default=None, description="Version source for the project."
    )
    components: dict[str, VersionSource] = Field(
        description="Version sources keyed by component name.", default_factory=dict
    )


class VersionDependency(Strict):
    variant: str | None = Field(
        default=None,
        description="Variant used when resolving the dependency repository’s version.",
    )


class VersioningSpec(VersionOverride):
    variants: dict[str, VersionOverride] = Field(
        description="Project and component version-source overrides keyed by variant name.",
        default_factory=dict,
    )
    dependencies: dict[str, VersionDependency] = Field(
        description="Other repositories whose versions should be resolved.",
        default_factory=dict,
    )


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
        if all(int(part) <= 9999 for part in (major, minor, patch)):
            result["sort_key"] = "_".join(
                f"{int(part):04d}" for part in (major, minor, patch)
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
