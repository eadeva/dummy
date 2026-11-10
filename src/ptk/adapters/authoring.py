"""Offline authoring resources and protected synchronization into .github."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from importlib import resources
from pathlib import Path, PurePosixPath

from ..authoring_bundle import manifest_content, source_files
from ..domain.errors import PtkError

MANIFEST = "ptk/manifest.json"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class AuthoringFiles:
    def bundle(self) -> dict[str, bytes]:
        base = resources.files("ptk").joinpath("resources", "authoring")
        if not base.is_dir():
            root = Path(__file__).resolve().parents[3]
            try:
                return {
                    name: path.read_bytes() for name, path in source_files(root).items()
                }
            except (OSError, ValueError) as exc:
                raise PtkError(
                    f"PTk authoring resources are unavailable: {exc}"
                ) from None
        result = {}

        def visit(folder, prefix=""):
            for entry in folder.iterdir():
                if entry.name == "__pycache__" or entry.name.endswith((".pyc", ".pyo")):
                    continue
                name = prefix + entry.name
                if entry.is_dir():
                    visit(entry, name + "/")
                else:
                    result[name] = entry.read_bytes()

        visit(base)
        return result

    def sync(
        self,
        root: Path,
        files: dict[str, bytes],
        *,
        version: str,
        check: bool,
        configuration_readme: tuple[str, bytes] | None = None,
    ) -> list[str]:
        """Return changed paths; protect custom edits and unrelated .github files."""
        root = root.resolve()
        github = root / ".github"

        def safe(name: str) -> Path:
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in name
                or not (
                    name.startswith(("ptk/", "skills/ptk-"))
                    or name == "agents/ptk-expert.agent.md"
                )
            ):
                raise PtkError(f"invalid managed authoring path: {name!r}")
            path = github.joinpath(*relative.parts)
            for candidate in (path, *path.parents):
                if candidate == root:
                    break
                if candidate.is_symlink() or candidate.is_junction():
                    raise PtkError(f"refusing symlinked authoring path: {candidate}")
                if candidate != path and candidate.exists() and not candidate.is_dir():
                    raise PtkError(
                        f"authoring directory is not a directory: {candidate}"
                    )
            if not path.resolve().is_relative_to(github):
                raise PtkError(f"authoring path escapes .github: {name}")
            return path

        manifest = safe(MANIFEST)
        previous = {}
        old_readme = None
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                previous = data["files"]
                old_readme = data.get("configuration_readme")
                if (
                    data["schema_version"] != 1
                    or not isinstance(previous, dict)
                    or not all(
                        isinstance(k, str) and isinstance(v, str)
                        for k, v in previous.items()
                    )
                ):
                    raise ValueError("invalid manifest fields")
                if MANIFEST in previous:
                    raise ValueError("manifest cannot manage itself")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise PtkError(f"invalid PTk authoring manifest: {exc}") from None
        changes, conflicts = [], []
        for name in sorted(set(files) | set(previous)):
            path = safe(name)
            current = path.read_bytes() if path.is_file() else None
            desired = files.get(name)
            if current == desired and not (path.exists() and not path.is_file()):
                continue
            changes.append(name)
            if path.exists() and (
                not path.is_file() or digest(current) != previous.get(name)
            ):
                conflicts.append(name)

        def readme_path(name):
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in name
                or relative.name != "README.md"
                or any(part in {".git", ".repo", ".ptk"} for part in relative.parts)
            ):
                raise PtkError(f"invalid configuration README path: {name!r}")
            if relative.parts[:2] in (
                (".github", "ptk"),
                (".github", "skills"),
                (".github", "agents"),
            ):
                raise PtkError(
                    "configuration README conflicts with the managed assistant bundle"
                )
            path = root.joinpath(*relative.parts)
            for candidate in (path, *path.parents):
                if candidate == root:
                    break
                if candidate.is_symlink() or candidate.is_junction():
                    raise PtkError(f"refusing symlinked README path: {candidate}")
                if candidate != path and candidate.exists() and not candidate.is_dir():
                    raise PtkError(f"README parent is not a directory: {candidate}")
            if not path.resolve().is_relative_to(root):
                raise PtkError("configuration README escapes repository")
            return path

        if old_readme is not None:
            if (
                not isinstance(old_readme, dict)
                or not isinstance(old_readme.get("path"), str)
                or not isinstance(old_readme.get("sha256"), str)
            ):
                raise PtkError("invalid configuration README provenance")
            readme_path(old_readme["path"])
        readme_changes = []
        next_readme = old_readme
        if configuration_readme is not None:
            name, value = configuration_readme
            desired = {name: value}
            if old_readme and old_readme["path"] != name:
                desired[old_readme["path"]] = None
            for rel, content in desired.items():
                path = readme_path(rel)
                if path == github / "ptk/README.md" or path == manifest:
                    raise PtkError(
                        "configuration README conflicts with the managed assistant bundle"
                    )
                current = path.read_bytes() if path.is_file() else None
                if current == content and not (path.exists() and not path.is_file()):
                    continue
                recorded = (
                    old_readme["sha256"]
                    if old_readme and old_readme["path"] == rel
                    else None
                )
                if path.exists() and (
                    not path.is_file() or digest(current) != recorded
                ):
                    conflicts.append(rel)
                readme_changes.append((path, content))
            next_readme = {"path": name, "sha256": digest(value)}
        if conflicts:
            raise PtkError(
                "preserving locally changed or unowned authoring files; move or reconcile them before setup:\n  "
                + "\n  ".join(conflicts)
            )
        content = manifest_content(files, version, next_readme)
        if not manifest.is_file() or manifest.read_bytes() != content:
            changes.append(MANIFEST)
        paths = changes + [
            path.relative_to(root).as_posix() for path, _ in readme_changes
        ]
        if check:
            return paths
        operations = [
            (safe(name), files.get(name)) for name in changes if name != MANIFEST
        ]
        operations += readme_changes
        if MANIFEST in changes:
            operations.append((manifest, content))
        for path, value in operations:
            if value is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=path.parent, delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(value)
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return paths
