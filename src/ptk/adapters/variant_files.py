"""Write validated generator output only into the owning step's build directory."""

import os
import tempfile
from pathlib import Path, PureWindowsPath

from ..domain.errors import PtkError


def variant_writer(generators):
    def generate(names, variant, folder, out, cancel):
        if variant is None or not variant.ok:
            raise PtkError("generators require a valid selected variant")
        folder = Path(folder)
        if any(path.is_symlink() for path in (folder, *folder.parents)):
            raise PtkError("generator output directory must not use symbolic links")
        root = folder.resolve()
        files = {}
        portable_names = set()
        for name in names:
            if cancel is not None and cancel.is_set():
                return
            if name not in generators:
                raise PtkError(f"generator '{name}' is not enabled")
            try:
                generated = generators[name](variant.model_copy(deep=True))
            except Exception as exc:
                raise PtkError(f"generator '{name}' failed: {exc}") from exc
            if not isinstance(generated, dict):
                raise PtkError(f"generator {name} must return filename -> text")
            for filename, content in generated.items():
                if not isinstance(filename, str) or not isinstance(content, str):
                    raise PtkError(
                        f"invalid generator output from {name}: expected filename -> text"
                    )
                relative = Path(filename)
                if (
                    not filename
                    or "\\" in filename
                    or relative.is_absolute()
                    or PureWindowsPath(filename).drive
                    or ".." in relative.parts
                ):
                    raise PtkError(
                        f"generator output must be inside the step directory: {filename}"
                    )
                target = root / relative
                if (
                    target == root
                    or not target.resolve().is_relative_to(root)
                    or any(p.is_symlink() for p in (target, *target.parents))
                ):
                    raise PtkError(
                        f"generator output must be inside the step directory without symlinks: {filename}"
                    )
                key = relative.as_posix().casefold()
                if key in portable_names:
                    raise PtkError(f"duplicate generator output: {filename}")
                if any(
                    key.startswith(other + "/") or other.startswith(key + "/")
                    for other in portable_names
                ):
                    raise PtkError(
                        f"conflicting generator file/directory output: {filename}"
                    )
                if target.exists() and not target.is_file():
                    raise PtkError(f"generator output is not a file: {filename}")
                if any(p.exists() and not p.is_dir() for p in target.parents):
                    raise PtkError(f"generator parent is not a directory: {filename}")
                try:
                    content.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise PtkError(
                        f"generator output is not UTF-8 text: {filename}"
                    ) from exc
                portable_names.add(key)
                files[target] = content
        # Check all generators and paths before replacing any file. Each file is
        # replaced atomically; there is no claim of a multi-file transaction.
        for target, content in files.items():
            if cancel is not None and cancel.is_set():
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    dir=target.parent,
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(content)
                os.replace(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            out(f"generated {target}")

    return generate
