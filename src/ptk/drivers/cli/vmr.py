"""ptk vmr: git-repo commands for virtual monorepos, with the git-repo shipped with ptk."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import rich_click as click

from ...adapters import git_repo
from ...domain.errors import PtkError
from .state import guarded


def _jobs():
    return str(min(os.cpu_count() or 4, 8))


def _sync(root, extra=()):
    git_repo.run(["sync", "-j", _jobs(), "--current-branch", *extra], root)


@click.group("vmr")
def vmr_group():
    """git-repo commands for the virtual monorepo (VMR).

    ptk ships git-repo (new VMRs need no download) and always runs it without pager and
    without the launcher's signature check. Commands not wrapped here: ptk vmr repo -- ARGS.
    """


@vmr_group.command("manifest")
@click.option(
    "-o",
    "--output",
    default="-",
    show_default=True,
    help="Output file; - prints to the console.",
)
@click.option(
    "--revision",
    "revisions",
    multiple=True,
    metavar="PROJECT=REVISION",
    help="Replace a project's commit, e.g. toyota_cgw=release/cgw_cs/1.1.0 (repeatable).",
)
@guarded
def manifest(output, revisions):
    """Write the revision-locked manifest: every repository at its checked-out commit."""
    root = git_repo.require_root(Path.cwd())
    overrides = {}
    for item in revisions:
        name, sep, revision = item.partition("=")
        if not sep or not name or not revision:
            raise PtkError(f"--revision expects PROJECT=REVISION, got {item!r}")
        overrides[name] = revision
    with tempfile.TemporaryDirectory(prefix="ptk-vmr-") as temp:
        locked = Path(temp) / "manifest.xml"
        git_repo.run(["manifest", "-r", "-o", str(locked)], root, capture=True)
        text = locked.read_text(encoding="utf-8")
    if overrides:
        text = git_repo.override_revisions(text, overrides)
    if output == "-":
        click.echo(text, nl=False)
    else:
        target = Path(output).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        click.echo(f"VMR manifest written to {target}", err=True)


@vmr_group.command("init")
@click.argument("manifest_url", required=False)
@click.option("-b", "--branch", help="Manifest repository branch, e.g. develop.")
@click.option(
    "--manifest",
    "manifest_file",
    help="vmr_manifest.xml (file or URL): reproduce exactly its commits, no manifest repository.",
)
@click.option(
    "--dir",
    "directory",
    type=click.Path(file_okay=False),
    help="New workspace folder (created if missing); default: the current folder.",
)
@click.option("--no-sync", is_flag=True, help="Only initialize, do not run repo sync.")
@guarded
def init(manifest_url, branch, manifest_file, directory, no_sync):
    """Create a new VMR workspace (repo init + repo sync).

    Without MANIFEST_URL and --manifest, the manifest repository of the VMR you are in is used.
    """
    target = Path(directory).resolve() if directory else Path.cwd().resolve()
    existing = git_repo.find_root(target)
    if existing is not None:
        raise PtkError(
            f"{target} is inside the VMR {existing}; choose an empty --dir, "
            "or switch this VMR with ptk vmr reinit"
        )
    if target.exists() and directory is None and any(target.iterdir()):
        raise PtkError(f"{target} is not empty; choose an empty --dir")
    if manifest_file and (manifest_url or branch):
        raise PtkError("--manifest replaces MANIFEST_URL and --branch")
    if manifest_file:
        args = [
            "init",
            "--standalone-manifest",
            "-u",
            git_repo.manifest_reference(manifest_file),
        ]
        saved = None
    else:
        if not manifest_url:
            current = git_repo.find_root(Path.cwd().resolve())
            manifest_url = git_repo.manifest_source(current)[0] if current else None
        if not manifest_url:
            raise PtkError(
                "no manifest repository: pass MANIFEST_URL, run inside a VMR, or use --manifest"
            )
        args = ["init", "-u", manifest_url, *(["-b", branch] if branch else [])]
        saved = manifest_url
    target.mkdir(parents=True, exist_ok=True)
    git_repo.run(args, target)
    if saved:
        (target / ".repo" / git_repo.SAVED_URL).write_text(
            saved + "\n", encoding="utf-8"
        )
    if not no_sync:
        _sync(target)
    click.echo(f"VMR initialized in {target}")


@vmr_group.command("reinit")
@click.option("-b", "--branch", help="Switch to this manifest repository branch.")
@click.option(
    "--manifest",
    "manifest_file",
    help="Switch to a vmr_manifest.xml (file or URL) with fixed commits.",
)
@click.option(
    "--manifest-url",
    help="Manifest repository; default: the current one (also after --manifest).",
)
@click.option(
    "--force", is_flag=True, help="Switch despite local changes or unpushed commits."
)
@click.option(
    "--no-sync", is_flag=True, help="Only re-initialize, do not run repo sync."
)
@guarded
def reinit(branch, manifest_file, manifest_url, force, no_sync):
    """Switch the VMR you are in to another manifest branch or vmr_manifest.xml."""
    root = git_repo.require_root(Path.cwd())
    if manifest_file and (branch or manifest_url):
        raise PtkError("--manifest replaces --branch and --manifest-url")
    if not (branch or manifest_file or manifest_url):
        raise PtkError("choose --branch, --manifest or --manifest-url")
    if not force:
        problems = git_repo.local_changes(root)
        if problems:
            raise PtkError(
                "local work would be carried into the other state or block the sync:\n  "
                + "\n  ".join(problems)
                + "\ncommit/push or stash it, or use --force"
            )
    current_url, standalone = git_repo.manifest_source(root)
    if manifest_file:
        if current_url:
            (root / ".repo" / git_repo.SAVED_URL).write_text(
                current_url + "\n", encoding="utf-8"
            )
        args = [
            "init",
            "--standalone-manifest",
            "-u",
            git_repo.manifest_reference(manifest_file),
        ]
    else:
        url = manifest_url or current_url
        if standalone and not url:
            raise PtkError("this VMR uses a vmr_manifest.xml; pass --manifest-url")
        # After a standalone manifest, git-repo needs the manifest repository again.
        args = [
            "init",
            *(["-u", url] if standalone or manifest_url else []),
            *(["-b", branch] if branch else []),
        ]
    git_repo.run(args, root)
    if not no_sync:
        _sync(root)
    click.echo(f"VMR {root} re-initialized")


@vmr_group.command("sync", context_settings={"ignore_unknown_options": True})
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
@guarded
def sync(extra):
    """Update every repository (repo sync -j<cores> --current-branch [EXTRA])."""
    _sync(git_repo.require_root(Path.cwd()), extra)


@vmr_group.command("status")
@guarded
def status():
    """Branch, commit and local changes of every repository (plus repo status)."""
    root = git_repo.require_root(Path.cwd())
    for path in git_repo.projects(root):
        name = path.relative_to(root).as_posix()
        branch = git_repo.git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=path)
        commit = git_repo.git("rev-parse", "--short=12", "HEAD", cwd=path) or "?"
        dirty = git_repo.git("status", "--porcelain", "--untracked-files=no", cwd=path)
        ahead = ""
        if branch:
            counts = git_repo.git(
                "rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=path
            )
            if counts:
                behind, ahead_count = counts.split()
                ahead = f" ahead {ahead_count}, behind {behind}"
        click.echo(
            f"{name:30} {branch or '(detached)':40} {commit}"
            f"{' modified' if dirty else ''}{ahead}"
        )
    git_repo.run(["status"], root)


@vmr_group.command(
    "repo",
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def repo(args):
    """Run any git-repo command: ptk vmr repo -- start feature/x --all."""
    result = subprocess.run(
        git_repo.command(list(args), Path.cwd()),
        env={**os.environ, **git_repo.ENV},
        check=False,
    )
    sys.exit(result.returncode)
