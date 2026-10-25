"""Filesystem adapter for non-overwriting project initialization."""

from pathlib import Path

from ..domain.errors import PtkError


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


class FileProjectScaffold:
    def create(self, target: Path, files: dict[str, str], *, dry_run: bool) -> bool:
        main = target / ".main.ptk.yml"
        ignore = target / ".gitignore"
        if _exists(target) and not target.is_dir():
            raise PtkError(f"project directory is not a directory: {target}")
        if _exists(main):
            raise PtkError(f"refusing to overwrite existing configuration: {main}")
        keep_ignore = _exists(ignore)
        if dry_run:
            return keep_ignore
        created: list[Path] = []
        try:
            target.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also protects against a concurrent initializer.
            with main.open("x", encoding="utf-8") as handle:
                created.append(main)
                handle.write(files[".main.ptk.yml"])
            if not keep_ignore:
                try:
                    with ignore.open("x", encoding="utf-8") as handle:
                        created.append(ignore)
                        handle.write(files[".gitignore"])
                except FileExistsError:
                    keep_ignore = True  # another process created it; preserve it
        except OSError as exc:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise PtkError(f"cannot initialize {target}: {exc}") from None
        return keep_ignore
