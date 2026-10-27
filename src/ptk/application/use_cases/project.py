"""Load and validate a ptk project (use case)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version
from pydantic import BaseModel, ValidationError

from ...domain.config import rules as config_rules
from ...domain.config import tree as t
from ...domain.config.defaults import apply_defaults, normalize_requirements
from ...domain.config.model import JOB_RE, MaintainersSpec, PtkConfig, WorkspaceSpec
from ...domain.config.schema_walk import unknown_keys
from ...domain.errors import ConfigError, Location, Problem
from ..ports import CX_FILE, LOCAL_FILE, MAINTAINERS_FILE, ConfigSource, HostEnvironment

_UNION_TAG = re.compile(
    r"^(str|int|float|bool|none|list\[.*\]|dict\[.*\]|literal\[.*\]|.*\[.*\]|function-.*)$",
    re.IGNORECASE,
)


@dataclass
class Project:
    config: PtkConfig
    root: Path
    main_file: Path
    tree: t.Node
    files: list[Path]
    layers: list[str]
    maintainers: MaintainersSpec | None = None
    ci: bool = False
    selected_tools: list[str] | None = None
    warnings: list[Problem] = field(default_factory=list)

    @property
    def config_root(self) -> Path:
        spec = self.config.repository
        return (self.root / spec.config_path).resolve() if spec else self.root

    def location(self, path: t.Path) -> Location | None:
        return t.locate(self.tree, path)


def validation_problems(
    model: type[BaseModel], tree: t.Node, *, skip_unknown: bool
) -> list[Problem]:
    """pydantic errors mapped to file:line (unknown keys handled separately)."""
    try:
        model.model_validate(t.to_plain(tree))
    except ValidationError as exc:
        problems = []
        model_names = {
            cls.__name__ for cls in BaseModel.__subclasses__()
        } | _all_model_names(model)
        for error in exc.errors():
            if error["type"] == "extra_forbidden" and skip_unknown:
                continue
            path = tuple(
                p
                for p in error["loc"]
                if not (
                    isinstance(p, str) and (p in model_names or _UNION_TAG.match(p))
                )
            )
            message = error["msg"].removeprefix("Value error, ")
            problems.append(
                Problem(message, t.display_path(tree, path), t.locate(tree, path))
            )
        return _dedupe(problems)
    return []


def _all_model_names(model: type[BaseModel]) -> set[str]:
    names: set[str] = set()
    stack = [model]
    while stack:
        cls = stack.pop()
        if cls.__name__ in names:
            continue
        names.add(cls.__name__)
        for field_info in cls.model_fields.values():
            for tp in _types_in(field_info.annotation):
                if isinstance(tp, type) and issubclass(tp, BaseModel):
                    stack.append(tp)
    return names


def _types_in(annotation: Any):
    from typing import get_args

    yield annotation
    for arg in get_args(annotation):
        yield from _types_in(arg)


def _dedupe(problems: list[Problem]) -> list[Problem]:
    seen: set[str] = set()
    result = []
    for p in problems:
        if str(p) not in seen:
            seen.add(str(p))
            result.append(p)
    return result


def parse_override(text: str) -> tuple[t.Path, Any]:
    if "=" not in text:
        raise ConfigError([Problem(f"--set expects PATH=VALUE, got {text!r}")])
    path_text, value_text = text.split("=", 1)
    try:
        path = t.parse_dotted(path_text.strip())
    except ValueError as exc:
        raise ConfigError([Problem(f"--set {text!r}: {exc}")]) from None
    try:
        value = yaml.safe_load(value_text) if value_text.strip() else ""
    except yaml.YAMLError:
        value = value_text
    return path, value


class LoadProject:
    def __init__(self, source: ConfigSource, host: HostEnvironment, ptk_version: str):
        self._source = source
        self._host = host
        self._version = ptk_version

    def execute(
        self,
        start: Path | None = None,
        *,
        config_file: Path | None = None,
        overrides: list[str] | tuple[str, ...] = (),
        ci: bool | None = None,
    ) -> Project:
        main = (
            config_file.resolve()
            if config_file
            else self._source.find_main(start or Path.cwd())
        )
        root = main.parent
        first_read = len(self._source.files)
        main_tree = self._source.read(main)
        marker = t.get(main_tree, ("virtual_monorepo",))
        if marker is not None and marker.value is True:
            raise ConfigError(
                [
                    Problem(
                        "this is a VMR workspace marker; select a member repository's .main.ptk.yml",
                        location=marker.loc,
                    )
                ]
            )
        metadata = t.get(main_tree, ("repository", "config_path"))
        config_root = (root / metadata.value).resolve() if metadata else root
        is_ci = self._host.is_ci() if ci is None else ci
        overlays = []
        for name, enabled in ((CX_FILE, is_ci), (LOCAL_FILE, True)):
            layer_file = config_root / name
            if enabled and self._source.exists(layer_file):
                overlays.append((name, self._source.read(layer_file)))

        # Conventional tool files are defaults: explicit main/includes win.
        # Files already included explicitly retain that placement and are not applied twice.
        tree = t.from_plain({})
        layers = []
        for filename in (
            "folder_structure.ptk.yml",
            "tools.ptk.yml",
            "versioning.ptk.yml",
            "workflow.ptk.yml",
            "artifactory_structure.ptk.yaml",
        ):
            conventional = config_root / filename
            if conventional not in self._source.files[
                first_read:
            ] and self._source.exists(conventional):
                tree = t.merge(tree, self._source.read(conventional))
                layers.append(filename)
        names = set()
        for candidate in [tree, main_tree, *(node for _, node in overlays)]:
            jobs = t.get(candidate, ("jobs",))
            if jobs is not None and jobs.is_map:
                names.update(n for n in jobs.value if JOB_RE.fullmatch(n))
        for name in sorted(names):
            tool_file = config_root / f"{name}.tools.ptk.yml"
            if tool_file not in self._source.files[first_read:] and self._source.exists(
                tool_file
            ):
                tree = t.merge(tree, self._source.read(tool_file))
                layers.append(tool_file.name)
        tree = t.merge(tree, main_tree)
        layers.append(main.name)
        for name, overlay in overlays:
            tree = t.merge(tree, overlay)
            layers.append(name)
        for text in overrides:
            path, value = parse_override(text)
            loc = Location(f"--set {text}")
            tree = t.merge(
                tree,
                normalize_requirements(t.overlay_for(path, t.from_plain(value, loc))),
            )
            layers.append(f"--set {path_text(path)}")

        tree = apply_defaults(tree)
        problems = unknown_keys(PtkConfig, tree)
        problems += validation_problems(PtkConfig, tree, skip_unknown=bool(problems))
        if problems:
            raise ConfigError(problems)
        config = PtkConfig.model_validate(t.to_plain(tree))
        effective_marker = t.get(tree, ("virtual_monorepo",))
        if (effective_marker is not None) != (marker is not None) or (
            marker is not None and effective_marker.value != marker.value
        ):
            raise ConfigError(
                [
                    Problem(
                        "virtual_monorepo must be defined in the entry file and cannot be overridden",
                        "virtual_monorepo",
                        t.locate(tree, ("virtual_monorepo",)),
                    )
                ]
            )
        original_repository = t.get(main_tree, ("repository",))
        effective_repository = (
            config.repository.model_dump() if config.repository else None
        )
        if original_repository is not None and effective_repository != t.to_plain(
            original_repository
        ):
            raise ConfigError(
                [
                    Problem(
                        "repository metadata must be defined in the entry file and cannot be overridden",
                        "repository",
                        t.locate(tree, ("repository",)),
                    )
                ]
            )
        semantic = [
            Problem(message, t.display_path(tree, path), t.locate(tree, path))
            for path, message in config_rules.validate(config)
        ]
        if semantic:
            raise ConfigError(semantic)
        self._check_version(config, tree)

        project = Project(
            config=config,
            root=root,
            main_file=main,
            tree=tree,
            files=list(dict.fromkeys(self._source.files)),
            layers=layers,
            ci=is_ci,
        )
        project.maintainers = self.maintainers(config_root)
        return project

    def maintainers(self, config_root: Path) -> MaintainersSpec | None:
        """Load the independent identity list, also usable at a VMR root."""
        maintainers_file = config_root / MAINTAINERS_FILE
        if self._source.exists(maintainers_file):
            m_tree = self._source.read(maintainers_file)
            m_problems = unknown_keys(MaintainersSpec, m_tree)
            m_problems += validation_problems(
                MaintainersSpec, m_tree, skip_unknown=bool(m_problems)
            )
            if m_problems:
                raise ConfigError(m_problems)
            return MaintainersSpec.model_validate(t.to_plain(m_tree))
        return None

    def _check_version(self, config: PtkConfig, tree: t.Node) -> None:
        if not config.ptk_version:
            return
        loc = t.locate(tree, ("ptk_version",))
        try:
            spec = SpecifierSet(config.ptk_version)
        except InvalidSpecifier:
            raise ConfigError(
                [
                    Problem(
                        f"invalid version range {config.ptk_version!r} (example: '>=0.1,<0.2')",
                        "ptk_version",
                        loc,
                    )
                ]
            ) from None
        if not spec.contains(Version(self._version), prereleases=True):
            raise ConfigError(
                [
                    Problem(
                        f"this project needs ptk {config.ptk_version}, but ptk {self._version} is running. "
                        f'Install the right version with: uv tool install "ptk{config.ptk_version}"',
                        "ptk_version",
                        loc,
                    )
                ]
            )


def path_text(path: t.Path) -> str:
    return t.format_path(path)


# --------------------------------------------------------------------------- queries


@dataclass
class ShowResult:
    value: Any
    sources: list[tuple[str, str]]  # (path, location) for every leaf


class ShowConfig:
    def execute(self, project: Project, dotted: str | None = None) -> ShowResult:
        path = t.parse_dotted(dotted) if dotted else ()
        node = t.get(project.tree, path)
        if node is None:
            parent = t.get(project.tree, path[:-1]) if path else None
            options = list(parent.value) if parent is not None and parent.is_map else []
            from ...domain.suggest import did_you_mean

            raise ConfigError(
                [
                    Problem(
                        f"no configuration value at '{dotted}'"
                        f"{did_you_mean(str(path[-1]), options) if path else ''}"
                    )
                ]
            )
        sources = [
            (t.format_path(path + p), str(loc))
            for p, loc in t.provenance(node).items()
            if t.get(node, p) is not None
            and not (t.get(node, p).is_map or t.get(node, p).is_list)
        ]
        return ShowResult(t.to_plain(node), sources)


class ExportSchema:
    """JSON Schema of the configuration, with steps in their written form."""

    def execute(self) -> dict[str, Any]:
        schema = PtkConfig.model_json_schema(by_alias=True)
        defs = schema.get("$defs", {})
        step = defs.get("StepSpec")
        if step:
            body = json.loads(json.dumps(step))
            body["properties"].pop("name", None)
            body["required"] = [r for r in body.get("required", []) if r != "name"]
            body["title"] = "Step"
            defs["StepBody"] = body
            entry = {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 1,
                "description": '- step-name: {run|uses|steps: ...}  or  - step-name: "command"',
                "additionalProperties": {
                    "anyOf": [
                        {"$ref": "#/$defs/StepBody"},
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
            }
            defs["StepEntry"] = entry
            text = json.dumps(schema).replace(
                '"#/$defs/StepSpec"', '"#/$defs/StepEntry"'
            )
            schema = json.loads(text)
            schema["$defs"].pop("StepSpec", None)
        node = schema.get("$defs", {}).get("WorkflowNode")
        if node:
            body = json.loads(json.dumps(node))
            body["properties"].pop("name", None)
            body["required"] = [r for r in body.get("required", []) if r != "name"]
            schema["$defs"]["WorkflowBody"] = body
            schema["$defs"]["WorkflowEntry"] = {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 1,
                "additionalProperties": {
                    "anyOf": [{"$ref": "#/$defs/WorkflowBody"}, {"type": "string"}]
                },
            }
            schema = json.loads(
                json.dumps(schema).replace(
                    '"#/$defs/WorkflowNode"', '"#/$defs/WorkflowEntry"'
                )
            )
            schema["$defs"].pop("WorkflowNode", None)
        schema["properties"]["include"] = {
            "anyOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ]
        }
        schema["properties"]["variants"]["anyOf"].append({"type": "string"})
        for definition in [schema, schema.get("$defs", {}).get("JobSpec", {})]:
            properties = definition.get("properties", {})
            if "requires_tools" in properties:
                properties["requires_tools"] = {
                    "anyOf": [
                        properties["requires_tools"],
                        {"type": "array", "items": {"type": "string"}},
                    ]
                }
        # Project content may be supplied entirely by includes.
        schema["required"] = []
        schema["properties"]["repository"] = {"$ref": "#/$defs/RepositorySpec"}
        # Authored omission means automatic discovery, not explicit standalone.
        schema["properties"]["virtual_monorepo"].pop("default", None)
        workspace = WorkspaceSpec.model_json_schema()
        schema["properties"]["members"] = workspace["properties"]["members"]
        schema["allOf"] = [
            {
                "if": {
                    "properties": {"virtual_monorepo": {"const": True}},
                    "required": ["virtual_monorepo"],
                },
                "then": {
                    "properties": {
                        key: False
                        for key in schema["properties"]
                        if key not in {"virtual_monorepo", "members"}
                    }
                },
                "else": {"required": ["repository"], "properties": {"members": False}},
            }
        ]
        schema["title"] = "ptk configuration (*.ptk.yml)"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        return schema
