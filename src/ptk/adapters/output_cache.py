"""Local output fingerprints and atomic receipts, without artifact copies."""

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


class LocalOutputCache:
    def __init__(self, root: Path):
        self.root = root / ".ptk" / "output-cache" / "v1"

    def _path(self, identity):
        return self.root / (hashlib.sha256(identity.encode()).hexdigest() + ".json")

    def read(self, identity):
        try:
            path = self._path(identity)
            if path.is_symlink() or path.stat().st_size > 4096:
                return None
            record = json.loads(path.read_text(encoding="utf-8"))
            return record if isinstance(record, dict) else None
        except (OSError, ValueError):
            return None

    def invalidate(self, identity):
        self._path(identity).unlink(missing_ok=True)

    def write(self, identity, record):
        self.root.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root, delete=False
            ) as file:
                name = file.name
                json.dump(record, file, sort_keys=True)
            os.replace(name, self._path(identity))
        finally:
            if name:
                Path(name).unlink(missing_ok=True)

    def fingerprint(self, paths, cancel):
        if not paths or cancel.is_set():
            return None
        digest = hashlib.sha256()

        def add(value):
            data = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)

        def visit(path):
            if cancel.is_set():
                raise OSError("cancelled")
            before = path.lstat()
            # Declared paths may be outside the repository, but symlinks and
            # special files are cache misses rather than unbounded traversals.
            if stat.S_ISREG(before.st_mode):
                add(["file", stat.S_IMODE(before.st_mode), before.st_size])
                with path.open("rb") as file:
                    if os.fstat(file.fileno()) != before:
                        raise OSError("output changed while opening")
                    while data := file.read(1024 * 1024):
                        if cancel.is_set():
                            raise OSError("cancelled")
                        digest.update(data)
            elif stat.S_ISDIR(before.st_mode):
                add(["directory", stat.S_IMODE(before.st_mode)])
                for child in sorted(path.iterdir(), key=lambda item: item.name):
                    add(child.name)
                    visit(child)
                add("end directory")
            else:
                raise OSError("output is not a regular file or directory")
            after = path.lstat()
            if (
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise OSError("output changed while hashing")

        try:
            for name in sorted(set(paths)):
                add(name)
                visit(Path(name))
        except (OSError, ValueError, RecursionError):
            return None
        return digest.hexdigest()
