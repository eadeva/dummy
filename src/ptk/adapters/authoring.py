"""Offline authoring resources and protected synchronization into .github."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from importlib import resources
from pathlib import Path, PurePosixPath

from ..authoring_bundle import source_files
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
                    f"PTK authoring resources are unavailable: {exc}"
                ) from None
        result = {}

        def visit(folder, prefix=""):
            for entry in folder.iterdir():
                name = prefix + entry.name
                if entry.is_dir():
                    visit(entry, name + "/")
                else:
                    result[name] = entry.read_bytes()

        visit(base)
        return result

    def sync(
        self, root: Path, files: dict[str, bytes], *, version: str, check: bool
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
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                previous = data["files"]
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
                raise PtkError(f"invalid PTK authoring manifest: {exc}") from None
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
        if conflicts:
            raise PtkError(
                "preserving locally changed or unowned authoring files; move or reconcile them before setup:\n  "
                + "\n  ".join(conflicts)
            )
        content = (
            json.dumps(
                {
                    "schema_version": 1,
                    "ptk_version": version,
                    "files": {
                        name: digest(value) for name, value in sorted(files.items())
                    },
                },
                indent=2,
            )
            + "\n"
        ).encode()
        if not manifest.is_file() or manifest.read_bytes() != content:
            changes.append(MANIFEST)
        if check:
            return changes
        for name in changes:
            path = safe(name)
            value = content if name == MANIFEST else files.get(name)
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
        return changes
