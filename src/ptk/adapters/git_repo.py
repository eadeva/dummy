"""git-repo for virtual monorepos: the source shipped with ptk, run with ptk's Python."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from ..domain.errors import PtkError
from ..resources.git_repo import VERSION
from .tools import default_tools_dir

# Kept by `ptk vmr reinit --manifest`: a standalone manifest replaces git-repo's manifest URL.
SAVED_URL = "ptk-manifest-url"
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
BRANCH = "stable"


def source() -> Path | None:
    """git-repo source added by packaging; None in a source checkout."""
    path = Path(str(resources.files("ptk.resources.git_repo") / "source"))
    return path if (path / "main.py").is_file() else None


def launcher() -> Path:
    return Path(str(resources.files("ptk.resources.git_repo") / "repo"))


def local_repository(environ=os.environ) -> Path | None:
    """Git repository of the shipped source: repo init clones it instead of downloading git-repo."""
    shipped = source()
    if shipped is None:
        return None
    target = default_tools_dir(environ) / "git-repo" / VERSION
    if (target / ".git").is_dir():
        return target
    staging = target.with_name(f"{target.name}.tmp{os.getpid()}")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(shipped, staging, ignore=shutil.ignore_patterns("__pycache__"))
    identity = {"GIT_AUTHOR_NAME": "ptk", "GIT_AUTHOR_EMAIL": "ptk@localhost"}
    env = {
        **os.environ,
        **identity,
        "GIT_COMMITTER_NAME": "ptk",
        "GIT_COMMITTER_EMAIL": "ptk@localhost",
    }
    plain = ["-c", "core.autocrlf=false", "-c", "commit.gpgsign=false"]
    for args in (
        ["init", "-q", "-b", BRANCH],
        ["add", "-A"],
        ["commit", "-q", "--no-verify", "-m", f"git-repo {VERSION} shipped with ptk"],
        ["tag", VERSION.split("-")[0]],
    ):
        result = subprocess.run(
            ["git", *plain, *args],
            cwd=staging,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            shutil.rmtree(staging, ignore_errors=True)
            raise PtkError(
                f"cannot prepare git-repo in {staging}: {result.stderr.strip()}"
            )
    try:
        staging.rename(target)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if not (target / ".git").is_dir():
            raise
    return target


def command(args, cwd) -> list[str]:
    """git-repo argv without pager; a new VMR gets git-repo from the shipped source."""
    argv = [sys.executable, str(launcher()), "--no-pager", *args]
    if args[:1] == ["init"]:
        if "--repo-url" not in args and find_root(Path(cwd).resolve()) is None:
            # Without a shipped source (source checkout) the launcher downloads git-repo.
            local = local_repository()
            if local is not None:
                argv += ["--repo-url", str(local), "--repo-rev", BRANCH]
        if "--no-repo-verify" not in args:
            argv.append("--no-repo-verify")
    if args[:1] == ["sync"] and "--no-repo-verify" not in args:
        argv.append("--no-repo-verify")
    return argv


ENV = {"GIT_PAGER": "cat", "PAGER": "cat"}


def find_root(start: Path) -> Path | None:
    for directory in [start, *start.parents]:
        if (directory / ".repo" / "manifests.git").is_dir():
            return directory
    return None


def require_root(start: Path) -> Path:
    root = find_root(start.resolve())
    if root is None:
        raise PtkError(
            f"{start} is not inside a VMR (no .repo folder); see ptk vmr init"
        )
    return root


def run(args, cwd, *, capture=False, check=True):
    """git-repo without pager and without the launcher's signature check."""
    result = subprocess.run(
        command(args, cwd),
        cwd=str(cwd),
        env={**os.environ, **ENV},
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode:
        detail = f": {result.stderr.strip()}" if capture and result.stderr else ""
        raise PtkError(f"repo {' '.join(args)} failed ({result.returncode}){detail}")
    return result


def git(*args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def manifest_source(root: Path) -> tuple[str | None, str | None]:
    """(manifest repository URL, standalone manifest URL) of a workspace."""
    manifests = root / ".repo" / "manifests.git"
    standalone = git("config", "--get", "manifest.standalone", cwd=manifests)
    # A standalone manifest replaces the origin URL; ptk kept the repository URL.
    url = (
        None
        if standalone
        else git("config", "--get", "remote.origin.url", cwd=manifests)
    )
    saved = root / ".repo" / SAVED_URL
    if not url and saved.is_file():
        url = saved.read_text(encoding="utf-8").strip() or None
    return url, standalone or None


def manifest_reference(value: str) -> str:
    """A local file becomes a file:// URL; URLs are passed unchanged."""
    if urlsplit(value).scheme in {"http", "https", "file"}:
        return value
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise PtkError(f"manifest file not found: {value}")
    return path.as_uri()


def projects(root: Path) -> list[Path]:
    output = run(["list", "-p"], root, capture=True).stdout
    return [root / line.strip() for line in output.splitlines() if line.strip()]


def local_changes(root: Path) -> list[str]:
    """Uncommitted tracked changes and commits on local branches that no remote has."""
    problems = []
    for path in projects(root):
        name = path.relative_to(root).as_posix()
        if git("status", "--porcelain", "--untracked-files=no", cwd=path):
            problems.append(f"{name}: uncommitted changes")
        unpushed = git("log", "--branches", "--not", "--remotes", "--oneline", cwd=path)
        if unpushed:
            count = len(unpushed.splitlines())
            problems.append(f"{name}: {count} commit(s) on local branches not pushed")
    return problems


def override_revisions(text: str, revisions: dict[str, str]) -> str:
    """Set project revisions (name or path), keeping the original branch as upstream."""
    root = ET.fromstring(text)  # noqa: S314 - output of the local `repo manifest -r`
    found = set()
    for project in root.iter("project"):
        for key in (project.get("name"), project.get("path")):
            if key in revisions:
                revision = revisions[key]
                project.set("revision", revision)
                if not SHA.fullmatch(revision):
                    for attribute in ("upstream", "dest-branch"):
                        project.attrib.pop(attribute, None)
                found.add(key)
                break
    missing = set(revisions) - found
    if missing:
        raise PtkError(f"unknown manifest project(s): {', '.join(sorted(missing))}")
    ET.indent(root, space="  ")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
        + "\n"
    )
