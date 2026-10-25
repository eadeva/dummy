"""Bounded VMR discovery, cached for one CLI invocation; no recursive walks."""

from __future__ import annotations

from pathlib import Path

from ..domain.config.tree import Node, get
from ..domain.errors import PtkError
from .config.yaml_loader import YamlConfigReader


def _git_workspace(directory: Path) -> Path | None:
    git = directory / ".git"
    try:
        if git.is_symlink() or git.is_junction():
            target = git.resolve(strict=True)
        elif git.is_file():
            text = git.read_text(encoding="utf-8").strip()
            if not text.startswith("gitdir:") or not text[7:].strip():
                return None
            target = (directory / text[7:].strip()).resolve(strict=True)
        else:
            return None
    except (OSError, RuntimeError, UnicodeError) as exc:
        raise PtkError(f"cannot resolve Git metadata at {git}: {exc}") from None
    if target.is_dir():
        for parent in target.parents:
            if parent.name == ".repo" and parent.is_dir():
                return parent.parent
    return None


class WorkspaceDiscovery:
    """Share metadata and member indexes between routing, credentials and versions."""

    def __init__(self):
        self._metadata: dict[Path, Node] = {}
        self._roots: dict[Path, Path | None] = {}
        self._members: dict[Path, dict[str, Path]] = {}

    def metadata(self, main: Path) -> Node:
        if main not in self._metadata:
            self._metadata[main] = YamlConfigReader().read(main, metadata_only=True)
        return self._metadata[main]

    def root(self, start: Path) -> Path | None:
        start = start.resolve()
        if start in self._roots:
            return self._roots[start]
        root = self._find_root(start)
        self._roots[start] = root
        return root

    def _find_root(self, start: Path) -> Path | None:
        for directory in (start, *start.parents):
            if directory in self._roots:
                return self._roots[directory]
            main = directory / ".main.ptk.yml"
            if main.is_file():
                flag = get(self.metadata(main), ("virtual_monorepo",))
                if flag is not None:
                    result = directory if flag.value else None
                    self._roots[directory] = result
                    return result
            # A .repo directory is a trigger only at the invocation directory.
            if directory == start and (directory / ".repo").is_dir():
                return directory
            git = directory / ".git"
            if main.is_file() or git.exists() or git.is_symlink():
                result = _git_workspace(directory)
                self._roots[directory] = result
                return result
        return None

    def repositories(self, root: Path) -> dict[str, Path]:
        root = root.resolve()
        if root not in self._members:
            self._members[root] = self._read_repositories(root)
            # Explicit VMR routing supplies context even for manual workspaces.
            for main in self._members[root].values():
                self._roots[main.parent] = root
        return self._members[root]

    def _member_path(self, root: Path, relative: str) -> Path:
        path = (root / relative).resolve()
        if (
            not relative.strip()
            or Path(relative).is_absolute()
            or path == root
            or not path.is_relative_to(root)
            or any(part in {".git", ".repo"} for part in Path(relative).parts)
        ):
            raise PtkError(
                f"VMR member path escapes workspace or is not a member directory: {relative!r}"
            )
        return path

    def _read_repositories(self, root: Path) -> dict[str, Path]:
        repo = root / ".repo"
        main = root / ".main.ptk.yml"
        if repo.is_dir():
            index = repo / "project.list"
            if not index.is_file():
                raise PtkError(
                    f"missing VMR project index: {index}; run 'repo sync' to populate it (recursive discovery is disabled)"
                )
            candidates = [
                self._member_path(root, line.strip())
                for line in index.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            if not main.is_file():
                raise PtkError(f"no VMR marker at {main}")
            metadata = self.metadata(main)
            flag = get(metadata, ("virtual_monorepo",))
            if flag is None or not flag.value:
                raise PtkError(f"not a VMR marker: {main}")
            members = get(metadata, ("members",))
            if members is not None and members.value is not None:
                candidates = [
                    self._member_path(root, member.value) for member in members.value
                ]
            else:
                candidates = [
                    path
                    for path in root.iterdir()
                    if path.is_dir()
                    and not path.is_symlink()
                    and not path.is_junction()
                ]
        result = {}
        for directory in sorted(set(candidates)):
            main = directory / ".main.ptk.yml"
            if not main.is_file():
                continue
            tree = self.metadata(main)
            flag = get(tree, ("virtual_monorepo",))
            if flag is not None:  # A marker or an explicitly standalone repository.
                continue
            alias = get(tree, ("repository", "alias"))
            if alias is None:
                raise PtkError(f"missing repository alias: {main}")
            if alias.value in result:
                raise PtkError(
                    f"duplicate repository alias {alias.value!r}: {result[alias.value]} and {main}"
                )
            result[alias.value] = main
        return result


def workspace_root(start: Path) -> Path | None:
    return WorkspaceDiscovery().root(start)


def repositories(root: Path) -> dict[str, Path]:
    return WorkspaceDiscovery().repositories(root)
