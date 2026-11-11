"""``ptk --docker``: run jobs with the PTk installed in the project's Docker image.

One container per repository is kept running and reused; it is recreated when the
image or the container settings change. On Windows the repository is mirrored to
the WSL disk with rsync (``docker.workspace: sync``) or used through /mnt (``mount``).
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import rich_click as click
from rich.markup import escape

from ...adapters.docker import DockerEngine
from ...adapters.locking import file_lock
from ...domain.config.substitution import to_text
from ...domain.errors import PtkError
from .access import AccessGroup
from .state import CliState, console, err_console, guarded, state_of

WORKDIR = "/workspace"
LABEL = "ptk.project"
# tini (--init) and sleep; more processes are leftovers of an interrupted run
IDLE_PROCESSES = 2
LOCK_TIMEOUT = 4 * 3600
_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


def _lock(key: str) -> threading.Lock:
    with _GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def container_name(project: Any) -> str:
    alias = project.config.repository.alias if project.config.repository else None
    slug = re.sub(r"[^a-z0-9_.-]+", "-", (alias or project.config.project.name).lower())
    digest = hashlib.sha256(str(project.root.resolve()).encode()).hexdigest()[:8]
    return f"ptk-{slug.strip('-') or 'project'}-{digest}"


def engine_for(project: Any, state: CliState) -> DockerEngine:
    spec = project.config.docker
    return DockerEngine(
        windows=state.app.host.os_name() == "windows",
        distro=spec.wsl_distro,
        environ=state.app.host.variables,
        interactive=sys.stdin.isatty() and sys.stdout.isatty(),
    )


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return to_text(value)


def container_argv(
    *,
    job: str,
    maintainer: bool,
    variant: str | None = None,
    all_variants: bool = False,
    params: Mapping[str, Any] | None = None,
    features: Mapping[str, str] | None = None,
    only_step: str | None = None,
    end: str | None = None,
    args_for: Mapping[str, list[str]] | None = None,
    passthrough: Iterable[str] = (),
    overrides: Iterable[str] = (),
    verbose: int = 0,
    clean: bool = False,
    re_run: bool = False,
    no_cache_ptk: bool = False,
    quiet: bool = False,
    setup: bool = False,
) -> list[str]:
    """The ``ptk`` command line run inside the container for one job."""
    argv = ["ptk", *(["-v"] * verbose)]
    for item in overrides:
        argv += ["-s", item]
    if variant:
        argv += ["-V", variant]
    argv += ["-c"] if clean else ["-rr"] if re_run else []
    argv += [*(["maintainer"] if maintainer else []), "run", job]
    for name, value in (params or {}).items():
        argv += ["-p", f"{name}={_text(value)}"]
    for name, value in (features or {}).items():
        argv += ["--feature", f"{name}={value}"]
    if all_variants:
        argv.append("--all-variants")
    if only_step:
        argv += ["--only-step", only_step]
    if end:
        argv += ["--to", end]
    for step, words in (args_for or {}).items():
        argv += ["--args-for", f"{step}={shlex.join(words)}"]
    argv += ["--no-cache-ptk"] if no_cache_ptk else []
    argv += ["-q"] if quiet else []
    argv += ["--setup"] if setup else []
    extra = list(passthrough)
    return [*argv, "--", *extra] if extra else argv


def job_secrets(state: CliState, project: Any, plans: Iterable[Any]) -> dict[str, str]:
    """Resolve the job's step secrets on the host for the container's env provider."""
    refs = {
        ref
        for plan in plans
        for step in plan.walk()
        for ref in step.spec.secrets.values()
    }
    if not refs:
        return {}
    credentials = state.app.credentials(project)
    values = {}
    for ref in sorted(refs):
        name, _, field_name = ref.partition(".")
        key = credentials.keys(name, field_name or None)[0]
        if value := credentials.resolve(ref):
            values[key.env_var] = value
    return values


@dataclass
class DockerRun:
    """Run jobs of one repository in its container."""

    state: CliState
    project: Any
    engine: DockerEngine
    out: Callable[[str], None] = field(
        default=lambda line: err_console.print(line, highlight=False)
    )
    _workspace: str | None = None
    _ready: bool = False
    _workdir: str = WORKDIR
    _told: bool = False

    @property
    def spec(self):
        return self.project.config.docker

    @property
    def name(self) -> str:
        return container_name(self.project)

    @property
    def sync(self) -> bool:
        return self.engine.windows and self.spec.workspace == "sync"

    def _builds(self) -> str:
        layout = self.project.config.layout
        return str(PurePosixPath(layout.root) / layout.builds)

    def _layout_dirs(self) -> list[str]:
        layout = self.project.config.layout
        root = PurePosixPath(layout.root)
        return [
            str(root / getattr(layout, part))
            for part in ("builds", "bin", "logs", "reports")
        ]

    @contextmanager
    def reserved(self):
        """One ptk --docker run per repository; a lock of a dead process is removed."""
        with file_lock(
            self.project.root / ".ptk" / "docker.lock",
            timeout=LOCK_TIMEOUT,
            waiting=lambda _: self.out(
                "[yellow]docker: waiting for another ptk --docker run in this repository[/]"
            ),
        ):
            yield

    def prepare(self) -> None:
        with _lock(self.name):
            if self._ready:
                return
            self.engine.check()
            self._login()
            image = self.spec.image
            self.out(f"[dim]docker: pulling {escape(image)}[/]")
            if not self.engine.pull(image):
                self.out(
                    f"[yellow]docker: pull of {escape(image)} failed; using the local image[/]"
                )
            image_id = self.engine.image_id(image)
            if image_id is None:
                raise PtkError(f"docker image {image} is not available")
            self._leftovers()
            root = self.engine.path(self.project.root)
            if self.sync:
                self._workspace = f"{self.engine.home()}/.ptk/mirrors/{self.name}"
                self._mirror(root)
            else:
                self._workspace = self._mounted_root()
            self._container(image_id)
            if self.sync:
                # The mirror is private to this run (reserved), so its job locks are stale.
                self.engine.call(
                    "rm", "-rf",
                    f"{self._workspace}/.ptk/locks",
                    f"{self._workspace}/.ptk/output-cleanup.lock",
                )  # fmt: skip
            self._ready = True

    def _mounted_root(self) -> str:
        """A VMR member's .git points into the workspace (.repo): mount the workspace root."""
        workspace = getattr(self.state.app, "workspace", None)
        top = workspace.root(self.project.root) if workspace is not None else None
        if top is None:
            return self.engine.path(self.project.root)
        member = self.project.root.resolve().relative_to(Path(top).resolve()).as_posix()
        if member != ".":
            self._workdir = f"{WORKDIR}/{member}"
        return self.engine.path(Path(top))

    def _leftovers(self) -> None:
        """Stop processes of an interrupted run before the workspace changes."""
        current = self.engine.container(self.name)
        if current is None or not current[0]:
            return
        if self.engine.processes(self.name) > IDLE_PROCESSES:
            self.out(
                "[yellow]docker: stopping leftover processes of an interrupted run[/]"
            )
            self.engine.restart(self.name)

    def _login(self) -> None:
        name = self.spec.credential
        if name is None:
            return
        credentials = self.state.app.credentials(self.project)
        spec = self.project.config.credentials[name]
        user = credentials.resolve(f"{name}.{spec.user_field or 'user'}")
        registry = self.spec.image.split("/", 1)[0]
        self.engine.login(
            registry,
            self.spec.login_user.replace("{user}", user),
            credentials.resolve(f"{name}.token"),
        )

    def _mirror(self, root: str) -> None:
        excludes = [f"--exclude=/{d}/" for d in self._layout_dirs()]
        self.out(
            f"docker: syncing the repository to WSL {escape(self._workspace or '')} "
            "(the first sync takes longest) ..."
        )
        started = time.monotonic()
        code = self.engine.rsync(
            "-a", "--delete", "--copy-unsafe-links", "--mkpath",
            *excludes, "--exclude=/.ptk/", "--exclude=.venv*/",
            f"{root}/", f"{self._workspace}/",
        )  # fmt: skip
        if code != 0:
            raise PtkError(f"rsync to the WSL mirror failed (exit {code})")
        self.out(f"docker: synced in {time.monotonic() - started:.1f}s")

    def _container(self, image_id: str) -> None:
        user = self.engine.user()
        mounts = [f"{self._workspace}:{WORKDIR}"]
        # The host uid may have no home in the image; caches (uv) need a writable one.
        env = {
            "HOME": f"{self._workdir}/.ptk/home",
            **(self.engine.proxy() or {}),
            **self.spec.env,
        }
        settings = {
            "image": image_id,
            "user": user,
            "mounts": mounts,
            "env": env,
            "run_args": self.spec.run_args,
        }
        digest = hashlib.sha256(
            json.dumps(settings, sort_keys=True).encode()
        ).hexdigest()[:16]
        current = self.engine.container(self.name)
        if current is not None and current[1] != digest:
            self.out(
                f"[dim]docker: image or settings changed; recreating {self.name}[/]"
            )
            self.engine.remove(self.name)
            current = None
        if current is None:
            self.out(f"[dim]docker: starting container {self.name}[/]")
            self.engine.create(
                self.name,
                self.spec.image,
                user=user,
                workdir=self._workdir,
                mounts=mounts,
                env=env,
                labels={LABEL: str(self.project.root), "ptk.config": digest},
                run_args=self.spec.run_args,
            )
        elif not current[0]:
            self.engine.start(self.name)
        # Tools look the user up (getpass, qacli); the host uid is unknown to the image.
        self.engine.ensure_user(self.name, user, env["HOME"])

    def run(self, argv: list[str], *, secrets: Mapping[str, str], cx: bool) -> int:
        self.prepare()
        host = self.state.app.host
        values = {
            "PTK_CX": "1" if cx else "0",
            **({"PTK_USER": user} if (user := host.user_id()) else {}),
            **{k: host.variables[k] for k in self.spec.keep if k in host.variables},
            **secrets,
        }
        self.out(f"[dim]docker: {escape(self.name)} $ {escape(shlex.join(argv))}[/]")
        try:
            return self.engine.exec(
                self.name, argv, workdir=self._workdir, values=values
            )
        except KeyboardInterrupt:
            self.out(
                "[yellow]docker: cancelled; processes still running in the container "
                "are stopped before the next ptk --docker run[/]"
            )
            return 130

    def copy_back(self, paths: Iterable[str]) -> None:
        """Windows mirror: copy one job's folders and outputs back; _builds stays in WSL."""
        if not self.sync or self._workspace is None:
            return
        root = self.project.root.resolve()
        parts = []
        for item in paths:
            try:
                parts.append(Path(item).resolve().relative_to(root).as_posix())
            except ValueError:
                continue
        sources = [f"{self._workspace}/./{p}" for p in dict.fromkeys(parts)]
        if sources:
            self.out("docker: copying results back to Windows ...")
            started = time.monotonic()
            code = self.engine.rsync(
                "-rlt", "--relative", "--ignore-missing-args", *sources,
                f"{self.engine.path(self.project.root)}/",
            )  # fmt: skip
            if code not in (0, 23, 24):
                err_console.print(
                    f"[yellow]docker: copying results back failed (rsync exit {code})[/]"
                )
            else:
                self.out(f"docker: copied back in {time.monotonic() - started:.1f}s")
        if self._told:
            return
        self._told = True
        builds = self._builds()
        unc = "\\\\wsl$\\" + self.engine.distro + self._workspace.replace("/", "\\")
        console.print(
            f"[yellow]docker: {escape(builds)} is not synced back to Windows; "
            f"it stays in WSL: {escape(unc)}\\{escape(builds.replace('/', chr(92)))}[/]",
            highlight=False,
        )


def job_paths(plan: Any) -> list[str]:
    """The job's own bin/log/report folders and declared outputs."""
    return [*plan.dirs.values(), *plan.outputs]


def session(
    state: CliState, project: Any, cache: dict[Path, DockerRun] | None = None
) -> DockerRun:
    if project.config.docker is None:
        raise PtkError(
            "--docker needs a 'docker' section (image, credential, wsl_distro) in the project configuration"
        )
    if state.app.host.is_docker() and "PTK_DOCKER" in state.app.host.variables:
        raise PtkError("--docker is not available inside the PTk Docker image")
    if cache is not None and project.root in cache:
        return cache[project.root]
    run = DockerRun(state, project, engine_for(project, state))
    if cache is not None:
        cache[project.root] = run
    return run


def runs_in_docker(spec: Any) -> bool:
    return spec.docker and not spec.gui


# --------------------------------------------------------------------------- commands


@click.group("docker", cls=AccessGroup, invoke_without_command=True)
@click.pass_context
def docker_group(ctx):
    """The container that ptk --docker keeps for this repository."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(docker_status)


@docker_group.command("status")
@click.pass_context
@guarded
def docker_status(ctx):
    """Show the image, container and workspace mode."""
    state = state_of(ctx)
    project = state.project()
    run = session(state, project)
    current = run.engine.container(run.name)
    spec = project.config.docker
    where = (
        f"WSL '{spec.wsl_distro}', {spec.workspace}"
        if run.engine.windows
        else "mounted"
    )
    status = "missing" if current is None else "running" if current[0] else "stopped"
    console.print(f"image:     {escape(spec.image)}", highlight=False)
    console.print(f"container: {run.name} ({status})", highlight=False)
    console.print(f"workspace: {escape(where)}", highlight=False)
    console.print(
        f"default:   {'on' if state.use_docker(project) else 'off'} (--docker/--no-docker)",
        highlight=False,
    )


@docker_group.command("stop")
@click.pass_context
@guarded
def docker_stop(ctx):
    """Stop the container; the next ptk --docker run starts it again."""
    state = state_of(ctx)
    run = session(state, state.project())
    console.print(
        f"{run.name}: " + ("stopped" if run.engine.stop(run.name) else "not running")
    )


@docker_group.command("remove")
@click.pass_context
@guarded
def docker_remove(ctx):
    """Remove the container; the WSL mirror (with _builds) is kept."""
    state = state_of(ctx)
    run = session(state, state.project())
    console.print(
        f"{run.name}: " + ("removed" if run.engine.remove(run.name) else "not found")
    )
