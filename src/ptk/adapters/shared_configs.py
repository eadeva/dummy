"""Fetch immutable Git blobs without checkout, hooks, filters or submodules."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..domain.errors import PtkError
from ..domain.shared_configs import relative_path
from .locking import file_lock

MAX_FILE = 100 * 1024 * 1024


class GitConfigFiles:
    @staticmethod
    def safe(root: Path, relative: str) -> Path:
        relative_path(relative)
        root = root.resolve()
        path = root / relative
        for candidate in (path, *path.parents):
            if candidate == root:
                break
            if candidate.is_symlink() or candidate.is_junction():
                raise PtkError(f"refusing linked configuration path: {relative}")
            if candidate != path and candidate.exists() and not candidate.is_dir():
                raise PtkError(f"configuration parent is not a directory: {relative}")
        if not path.resolve().is_relative_to(root):
            raise PtkError("configuration path escapes repository")
        return path

    def transaction(self, root):
        return file_lock(self.safe(root, ".ptk/config-sync.lock"))

    def read(self, root, relative):
        path = self.safe(root, relative)
        if not path.exists():
            return None, None
        if not path.is_file():
            raise PtkError(
                f"configuration destination is not a regular file: {relative}"
            )
        if path.stat().st_size > MAX_FILE:
            raise PtkError(f"configuration exceeds 100 MiB: {relative}")
        mode = 0o755 if os.name != "nt" and path.stat().st_mode & 0o111 else 0o644
        if not path.stat().st_mode & 0o222:
            mode &= ~0o222
        return path.read_bytes(), mode

    def write(self, root, relative, content, mode):
        path = self.safe(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            temporary.chmod(mode)
            original_mode = path.stat().st_mode if path.exists() else None
            if os.name == "nt" and original_mode is not None:
                path.chmod(original_mode | 0o200)
            try:
                os.replace(temporary, path)
            except OSError:
                if original_mode is not None and path.exists():
                    path.chmod(original_mode)
                raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def git(directory, *args, allow_failure=False):
        try:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "protocol.ext.allow=never",
                    "--git-dir",
                    str(directory),
                    *args,
                ],
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                capture_output=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PtkError(
                "cannot run Git for external configurations; check Git availability and authentication"
            ) from exc
        if result.returncode and not allow_failure:
            # Git stderr can contain credential-helper output. Do not echo it.
            raise PtkError(
                f"Git {args[0]} failed for external configurations; check repository access and the pinned revision"
            )
        return result

    def snapshot(self, root, source, pinned, paths):
        repository = source.repository
        if "://" not in repository and not re.match(r"[^/]+@[^:]+:", repository):
            repository = str((root / repository).resolve())
        key = hashlib.sha256(repository.encode()).hexdigest()
        cache = self.safe(root, f".ptk/config-sources/{key}.git")
        if not cache.exists():
            cache.mkdir(parents=True)
            self.git(cache, "init", "--bare", str(cache))
        commit = pinned
        if commit is not None and not re.fullmatch(
            r"[0-9a-f]{40}|[0-9a-f]{64}", commit
        ):
            raise PtkError("invalid pinned configuration commit")
        if commit is None and re.fullmatch(
            r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", source.revision
        ):
            commit = source.revision.lower()
        present = (
            commit
            and self.git(
                cache, "cat-file", "-e", commit + "^{commit}", allow_failure=True
            ).returncode
            == 0
        )
        if not present:
            target = commit or "refs/tags/" + source.revision
            self.git(cache, "fetch", "--no-tags", "--depth=1", "--", repository, target)
            resolved = (
                self.git(cache, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
                .stdout.decode()
                .strip()
            )
            if commit is not None and commit != resolved:
                raise PtkError("configuration commit did not match requested revision")
            commit = resolved
        contents = {}
        for path in dict.fromkeys(paths):
            relative_path(path)
            if path.endswith("/"):
                listing = self.git(
                    cache, "ls-tree", "-r", "-z", commit, "--", path[:-1]
                ).stdout
                entries = [e for e in listing.split(b"\0") if e]
                if not entries:
                    raise PtkError(f"configuration source folder not found: {path}")
                for entry in entries:
                    metadata, actual = entry.split(b"\t", 1)
                    mode, kind, blob = metadata.decode().split()
                    name = actual.decode()
                    if not name.startswith(path):
                        raise PtkError(f"configuration source folder not found: {path}")
                    contents[name] = self._blob(cache, name, mode, kind, blob)
                continue
            tree = self.git(cache, "ls-tree", "-z", commit, "--", path).stdout
            entries = tree.split(b"\0")
            if len(entries) != 2 or not entries[0]:
                raise PtkError(f"configuration source file not found: {path}")
            metadata, actual = entries[0].split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            if actual.decode() != path:
                raise PtkError(f"configuration source file not found: {path}")
            contents[path] = self._blob(cache, path, mode, kind, blob)
        return commit, contents

    def _blob(self, cache, path, mode, kind, blob):
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise PtkError(
                f"configuration source must be a regular Git file, not a link/directory/submodule: {path}"
            )
        size = int(self.git(cache, "cat-file", "-s", blob).stdout)
        if size > MAX_FILE:
            raise PtkError(f"configuration source exceeds 100 MiB: {path}")
        return (
            self.git(cache, "cat-file", "blob", blob).stdout,
            int(mode, 8) & 0o777,
        )
