"""Read one located YAML mapping; project discovery lives in FileConfigSource.

Includes and merge directives are rejected. Every file contributes its full
schema path and the application combines disjoint fields with merge_unique.
YAML anchors within a document remain supported.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import yaml
from pydantic import ValidationError

from ...domain.config.defaults import normalize_requirements
from ...domain.config.model import RepositorySpec, WorkspaceSpec
from ...domain.config.tree import Node, to_plain
from ...domain.errors import ConfigError, Location, Problem


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
        self.files: list[Path] = []  # every file read, in order
        self._display_paths: dict[Path, str] = {}
        self._active_nodes: set[int] = set()
        self.fingerprints: dict[str, str] = {}

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
            data = path.read_bytes()
            text = data.decode("utf-8")
            self.fingerprints[str(path)] = sha256(data).hexdigest()
        except (OSError, UnicodeError) as exc:
            raise ConfigError(
                [Problem(f"cannot read {_display(path, self.display_root)}: {exc}")]
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
        if "include" in tree.value or isinstance(
            tree.value.get("variants", Node(None)).value, str
        ):
            raise ConfigError(
                [
                    Problem(
                        "includes are no longer supported: remove include and give each *.ptk.yml file its full schema path (for example variants: {variants: {...}})",
                        location=tree.loc,
                    )
                ]
            )
        return normalize_requirements(tree)

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
        if id(node) in self._active_nodes:
            raise ConfigError(
                [Problem("cyclic YAML alias", location=self._loc(node, path))]
            )
        self._active_nodes.add(id(node))
        try:
            return self._construct_value(node, path, loader, stack)
        finally:
            self._active_nodes.remove(id(node))

    def _construct_value(
        self, node: yaml.Node, path: Path, loader: _Loader, stack: tuple[Path, ...]
    ) -> Node:
        loc = self._loc(node, path)
        tag = node.tag
        if tag in ("!include", "!replace", "!append"):
            raise ConfigError(
                [
                    Problem(
                        f"{tag} is no longer supported: configuration files are discovered automatically and cannot overwrite values",
                        location=loc,
                    )
                ]
            )
        if tag.startswith("!"):
            raise ConfigError(
                [
                    Problem(
                        f"unknown tag {tag}",
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
