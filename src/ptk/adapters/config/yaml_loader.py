"""YAML configuration source (adapter).

Loads ``.ptk.yml`` and everything it pulls in into one located ``Node`` tree:

* ``include: [patterns]`` at the top of a file: listed files/globs are merged
  in order, then the file itself is merged on top (the including file wins)
* ``!include path-or-glob`` anywhere: inserts the file(s) at that place; for a
  glob, mappings are merged and lists concatenated
* ``!replace`` / ``!append`` mark how a value merges into lower layers
* ``variants: path/to/file.yml`` (a plain string) is sugar for ``!include``
* duplicate keys and include cycles are errors with ``file:line``
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from ...domain.config.defaults import normalize_requirements
from ...domain.config.model import RepositorySpec, WorkspaceSpec
from ...domain.config.tree import Node, merge, to_plain
from ...domain.errors import ConfigError, Location, Problem

INCLUDE_SUGAR_KEYS = (
    "variants",
)  # top-level keys whose string value means "include this file"


class _Loader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    """SafeLoader that only composes nodes; we construct values ourselves."""


def _display(path: Path, root: Path | None) -> str:
    if root:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


class YamlConfigReader:
    def __init__(self, display_root: Path | None = None):
        self.display_root = display_root
        self.entry_bases: dict[Path, Path] = {}
        self.files: list[Path] = []  # every file read, in order
        self._display_paths: dict[Path, str] = {}

    # ------------------------------------------------------------------ public

    def read(
        self,
        path: Path,
        *,
        _stack: tuple[Path, ...] = (),
        require_mapping: bool = True,
        metadata_only: bool = False,
    ) -> Node:
        path = path.resolve()
        if path.name == ".gen.version.ptk.yml":
            raise ConfigError(
                [Problem("generated version snapshots are not configuration inputs")]
            )
        if path in _stack:
            chain = " -> ".join(_display(p, self.display_root) for p in (*_stack, path))
            raise ConfigError([Problem(f"include cycle: {chain}")])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(
                [
                    Problem(
                        f"cannot read {_display(path, self.display_root)}: {exc.strerror}"
                    )
                ]
            ) from None
        self.files.append(path)
        loader = _Loader(text)
        try:
            node = loader.get_single_node()
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            loc = Location(
                _display(path, self.display_root), mark.line + 1 if mark else 0
            )
            raise ConfigError(
                [Problem(f"invalid YAML: {getattr(exc, 'problem', exc)}", location=loc)]
            ) from None
        finally:
            loader.dispose()
        if node is None:
            return Node({}, Location(_display(path, self.display_root), 1))
        stack = (*_stack, path)
        base_file = path
        if path.name == ".main.ptk.yml":
            flags = (
                [v for k, v in node.value if k.value == "virtual_monorepo"]
                if isinstance(node, yaml.MappingNode)
                else []
            )
            if len(flags) > 1:
                raise ConfigError(
                    [
                        Problem(
                            "duplicate key 'virtual_monorepo'",
                            location=self._loc(flags[1], path),
                        )
                    ]
                )
            flag = None
            if flags:
                if flags[0].tag != "tag:yaml.org,2002:bool":
                    raise ConfigError(
                        [
                            Problem(
                                "virtual_monorepo must be a boolean",
                                location=self._loc(flags[0], path),
                            )
                        ]
                    )
                flag = self._construct(flags[0], path, loader, stack)
            if flag is not None and flag.value:
                # Workspace markers have no includes or project configuration.
                unknown = [
                    k
                    for k, _ in node.value
                    if k.value not in WorkspaceSpec.model_fields
                ]
                if unknown:
                    raise ConfigError(
                        [
                            Problem(
                                f"unknown workspace field {k.value!r}",
                                location=self._loc(k, path),
                            )
                            for k in unknown
                        ]
                    )
                tree = self._literal_metadata(node, path, loader, stack)
                try:
                    WorkspaceSpec.model_validate(to_plain(tree))
                except ValidationError as exc:
                    raise ConfigError([Problem(str(exc), location=tree.loc)]) from None
                return tree
            # Read discovery metadata before resolving any include (including tags).
            entries = (
                [v for k, v in node.value if k.value == "repository"]
                if isinstance(node, yaml.MappingNode)
                else []
            )
            if len(entries) != 1:
                raise ConfigError(
                    [
                        Problem(
                            "entry file requires repository.alias and repository.config_path",
                            location=Location(str(path)),
                        )
                    ]
                )
            metadata = self._literal_metadata(entries[0], path, loader, stack)
            try:
                spec = RepositorySpec.model_validate(to_plain(metadata))
            except ValidationError as exc:
                raise ConfigError([Problem(str(exc), location=metadata.loc)]) from None
            directory = (path.parent / spec.config_path).resolve()
            if Path(spec.config_path).is_absolute() or not directory.is_relative_to(
                path.parent
            ):
                raise ConfigError(
                    [
                        Problem(
                            "repository.config_path must stay within the repository",
                            location=metadata.loc,
                        )
                    ]
                )
            if not directory.is_dir():
                raise ConfigError(
                    [
                        Problem(
                            f"configuration directory does not exist: {directory}",
                            location=metadata.loc,
                        )
                    ]
                )
            # Only the entry file changes its include base. Fragments remain relative
            # to their own containing directory; diagnostics keep the real filename.
            self.entry_bases[path] = directory
            if metadata_only:
                values = {"repository": metadata}
                if flag is not None:
                    values["virtual_monorepo"] = flag
                return Node(values, self._loc(node, path))
        tree = self._construct(node, base_file, loader, stack)
        if not tree.is_map:
            if require_mapping:
                raise ConfigError(
                    [Problem("top level must be a mapping", location=tree.loc)]
                )
            return tree
        tree = self._apply_top_level_includes(normalize_requirements(tree), path, stack)
        marker = tree.value.get("virtual_monorepo")
        original = flag if path.name == ".main.ptk.yml" else None
        if (marker is not None) != (original is not None) or (
            marker is not None and marker.value != original.value
        ):
            raise ConfigError(
                [
                    Problem(
                        "virtual_monorepo must be defined in the entry file and cannot be overridden",
                        location=tree.loc,
                    )
                ]
            )
        return tree

    # ------------------------------------------------------------------ construction

    def _loc(self, node: yaml.Node, path: Path) -> Location:
        if path not in self._display_paths:
            self._display_paths[path] = _display(path, self.display_root)
        return Location(self._display_paths[path], node.start_mark.line + 1)

    def _literal_metadata(
        self, node: yaml.Node, path: Path, loader: _Loader, stack: tuple[Path, ...]
    ) -> Node:
        """Discovery cannot read includes or execute merge directives."""

        def check(item: yaml.Node, ancestors: frozenset[int]) -> None:
            if id(item) in ancestors or not item.tag.startswith("tag:yaml.org,2002:"):
                raise ConfigError(
                    [
                        Problem(
                            "discovery metadata must be literal YAML without tags or cycles",
                            location=self._loc(item, path),
                        )
                    ]
                )
            if isinstance(item, yaml.MappingNode):
                children = [part for pair in item.value for part in pair]
            elif isinstance(item, yaml.SequenceNode):
                children = item.value
            else:
                children = []
            for child in children:
                check(child, ancestors | {id(item)})

        check(node, frozenset())
        return self._construct(node, path, loader, stack)

    def _construct(
        self, node: yaml.Node, path: Path, loader: _Loader, stack: tuple[Path, ...]
    ) -> Node:
        loc = self._loc(node, path)
        tag = node.tag
        if tag == "!include":
            if not isinstance(node, yaml.ScalarNode):
                raise ConfigError(
                    [Problem("!include expects a file path or glob", location=loc)]
                )
            return self._include(str(node.value), path, loc, stack)
        if tag in ("!replace", "!append"):
            op = tag[1:]
            inner = self._construct_untagged(node, path, loader, stack)
            if op == "append" and not inner.is_list:
                raise ConfigError([Problem("!append expects a list", location=loc)])
            inner.op = op  # type: ignore[assignment]
            return inner
        if tag.startswith("!"):
            raise ConfigError(
                [
                    Problem(
                        f"unknown tag {tag} (allowed: !include, !replace, !append)",
                        location=loc,
                    )
                ]
            )
        return self._construct_untagged(node, path, loader, stack)

    def _construct_untagged(
        self, node: yaml.Node, path: Path, loader: _Loader, stack: tuple[Path, ...]
    ) -> Node:
        loc = self._loc(node, path)
        if isinstance(node, yaml.MappingNode):
            explicit = sum(
                1 for k, _ in node.value if k.tag != "tag:yaml.org,2002:merge"
            )
            loader.flatten_mapping(node)  # YAML merge keys (<<: *anchor) come first
            merged_count = len(node.value) - explicit
            values: dict[str, Node] = {}
            key_locs: dict[str, Location] = {}
            explicit_keys: set[str] = set()
            for index, (key_node, value_node) in enumerate(node.value):
                key = loader.construct_object(key_node, deep=True)
                if not isinstance(key, (str, int, float, bool)):
                    raise ConfigError(
                        [
                            Problem(
                                "mapping keys must be scalars",
                                location=self._loc(key_node, path),
                            )
                        ]
                    )
                key = str(key)
                if (
                    index >= merged_count
                ):  # explicit keys may override merged ones, not each other
                    if key in explicit_keys:
                        raise ConfigError(
                            [
                                Problem(
                                    f"duplicate key '{key}'",
                                    location=self._loc(key_node, path),
                                )
                            ]
                        )
                    explicit_keys.add(key)
                values[key] = self._construct(value_node, path, loader, stack)
                key_locs[key] = self._loc(key_node, path)
            return Node(values, loc, key_locs=key_locs)
        if isinstance(node, yaml.SequenceNode):
            return Node(
                [self._construct(v, path, loader, stack) for v in node.value], loc
            )
        if isinstance(node, yaml.ScalarNode) and node.tag.startswith(
            "tag:yaml.org,2002:"
        ):
            return Node(loader.construct_object(node, deep=True), loc)
        return Node(loader.construct_scalar(node), loc)  # pragma: no cover

    # ------------------------------------------------------------------ includes

    def _resolve_pattern(
        self, pattern: str, base_file: Path, loc: Location
    ) -> list[Path]:
        expanded = os.path.expandvars(os.path.expanduser(pattern))
        full = (
            Path(expanded)
            if os.path.isabs(expanded)
            else self.entry_bases.get(base_file, base_file.parent) / expanded
        )
        if any(ch in expanded for ch in "*?["):
            matches = sorted(
                Path(p)
                for p in glob.glob(str(full), recursive=True)
                if Path(p).is_file() and Path(p).name != ".gen.version.ptk.yml"
            )
            return matches  # an empty glob is fine (optional fragments)
        if not full.is_file():
            raise ConfigError(
                [Problem(f"included file not found: {pattern}", location=loc)]
            )
        return [full]

    def _include(
        self, pattern: str, base_file: Path, loc: Location, stack: tuple[Path, ...]
    ) -> Node:
        files = self._resolve_pattern(pattern, base_file, loc)
        if not files:
            return Node({}, loc)
        nodes = [self.read(f, _stack=stack, require_mapping=False) for f in files]
        if len(nodes) == 1:
            return nodes[0]
        if all(n.is_list for n in nodes):
            return Node([item for n in nodes for item in n.value], loc)
        if all(n.is_map for n in nodes):
            result: Node | None = None
            for n in nodes:
                result = merge(result, n)
            assert result is not None
            return result
        raise ConfigError(
            [Problem(f"!include {pattern}: files mix mappings and lists", location=loc)]
        )

    def _apply_top_level_includes(
        self, tree: Node, path: Path, stack: tuple[Path, ...]
    ) -> Node:
        for key in INCLUDE_SUGAR_KEYS:
            value = tree.value.get(key)
            if value is not None and isinstance(value.value, str):
                tree.value[key] = self._include(
                    value.value, path, value.loc or Location(str(path)), stack
                )
        include = tree.value.pop("include", None)
        tree.key_locs.pop("include", None)
        if include is None:
            return tree
        patterns = include.value if include.is_list else [include]
        base: Node | None = None
        for item in patterns:
            if not isinstance(item.value, str):
                raise ConfigError(
                    [
                        Problem(
                            "include entries must be file paths or globs",
                            location=item.loc,
                        )
                    ]
                )
            for file in self._resolve_pattern(
                item.value, path, item.loc or Location(str(path))
            ):
                base = merge(base, self.read(file, _stack=stack))
        return merge(base, tree) if base is not None else tree
