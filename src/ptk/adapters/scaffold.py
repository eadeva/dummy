"""Non-overwriting multi-file scaffolding with preflight and rollback."""

from pathlib import Path

from ..domain.errors import PtkError


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


class FileProjectScaffold:
    def create(self, target: Path, files: dict[str, str], *, dry_run: bool) -> bool:
        if _exists(target) and not target.is_dir():
            raise PtkError(f"project directory is not a directory: {target}")
        for name in files:
            path = target / name
            if name != ".gitignore" and _exists(path):
                raise PtkError(f"refusing to overwrite existing configuration: {path}")
            if not path.resolve().is_relative_to(target.resolve()):
                raise PtkError(f"scaffold path escapes repository: {path}")
            for parent in path.parents:
                if parent == target.parent:
                    break
                if _exists(parent) and not parent.is_dir():
                    raise PtkError(
                        f"configuration directory is not a directory: {parent}"
                    )
        ignore = target / ".gitignore"
        kept = _exists(ignore)
        if kept and (ignore.is_symlink() or not ignore.is_file()):
            raise PtkError(".gitignore must be a regular file")
        if dry_run:
            return kept
        created = []
        try:
            for name, content in files.items():
                if name == ".gitignore":
                    continue
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as handle:
                    created.append(path)
                    handle.write(content)
            # Append only missing rules, preserving existing user content.
            old = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
            rules = [
                s
                for s in files[".gitignore"].splitlines()
                if s and not s.startswith("#") and s not in old.splitlines()
            ]
            if rules:
                with ignore.open("a", encoding="utf-8") as handle:
                    handle.write(
                        ("\n" if old and not old.endswith("\n") else "")
                        + "# ptk generated workspace and local overrides\n"
                        + "\n".join(rules)
                        + "\n"
                    )
        except OSError as exc:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise PtkError(f"cannot initialize {target}: {exc}") from None
        return kept
