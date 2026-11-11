"""Docker Engine access for ``ptk --docker``: directly on Linux, inside WSL on Windows.

Windows uses the Docker Engine of a WSL distribution (no Docker Desktop): every
command runs as ``wsl -d DISTRO --exec ...``. Secret values only travel in the
environment (forwarded into WSL with ``WSLENV``), never on a command line.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..domain.errors import PtkError

Runner = Callable[..., Any]  # subprocess.run compatible


class DockerEngine:
    def __init__(
        self,
        *,
        windows: bool,
        distro: str,
        run: Runner = subprocess.run,
        environ: Mapping[str, str] | None = None,
        interactive: bool = False,
    ):
        self.windows = windows
        self.distro = distro
        self._run = run
        self._environ = dict(os.environ if environ is None else environ)
        self._interactive = interactive

    def command(self, *argv: str) -> list[str]:
        return ["wsl", "-d", self.distro, "--exec", *argv] if self.windows else [*argv]

    def call(
        self,
        *argv: str,
        values: Mapping[str, str] | None = None,
        stdin: str | None = None,
        capture: bool = True,
        check: bool = True,
    ):
        env = dict(self._environ)
        if values:
            env.update(values)
            if self.windows:
                env["WSLENV"] = ":".join(filter(None, [env.get("WSLENV", ""), *values]))
        try:
            result = self._run(
                self.command(*argv),
                env=env,
                input=stdin,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=capture,
                check=False,
            )
        except FileNotFoundError:
            tool = "wsl" if self.windows else argv[0]
            raise PtkError(f"'{tool}' was not found; ptk --docker needs it") from None
        if check and result.returncode != 0:
            lines = ((result.stderr or "") + (result.stdout or "")).strip().splitlines()
            raise PtkError(
                f"'{' '.join(argv[:2])}' failed (exit {result.returncode})"
                + (f": {lines[-1]}" if lines else "")
            )
        return result

    # -- environment -----------------------------------------------------------

    def check(self) -> None:
        if self.windows:
            try:
                listing = self._run(
                    ["wsl", "-l", "-q"], capture_output=True, check=False
                )
            except FileNotFoundError:
                raise PtkError(
                    "WSL is not installed; ptk --docker uses Docker Engine in WSL"
                ) from None
            raw = listing.stdout or b""
            text = raw.decode("utf-16-le", "replace") if isinstance(raw, bytes) else raw
            names = {line.strip().strip("\x00") for line in text.splitlines()}
            if self.distro not in names:
                raise PtkError(
                    f"WSL distribution '{self.distro}' is not installed; "
                    f"install it with: wsl --install -d {self.distro}, then install Docker Engine in it"
                )
        result = self.call(
            "docker", "version", "--format", "{{.Server.Version}}", check=False
        )
        if result.returncode != 0:
            where = f" in WSL '{self.distro}'" if self.windows else ""
            raise PtkError(
                f"Docker Engine is not available{where}: "
                + ((result.stderr or "").strip().splitlines() or ["no answer"])[-1]
            )

    def path(self, path: Path) -> str:
        if not self.windows:
            return str(path)
        return self.call("wslpath", "-a", path.as_posix()).stdout.strip()

    def home(self) -> str:
        if not self.windows:
            return str(Path.home())
        return self.call("sh", "-c", 'printf %s "$HOME"').stdout.strip()

    def user(self) -> str:
        if not self.windows and hasattr(os, "getuid"):
            return f"{os.getuid()}:{os.getgid()}"
        uid = self.call("id", "-u").stdout.strip()
        gid = self.call("id", "-g").stdout.strip()
        return f"{uid}:{gid}"

    # -- images and containers --------------------------------------------------

    def proxy(self) -> dict[str, str]:
        """The engine's proxy as environment variables, host names replaced by addresses."""
        result = self.call(
            "docker", "info", "--format",
            "{{.HTTPProxy}}|{{.HTTPSProxy}}|{{.NoProxy}}", check=False,
        )  # fmt: skip
        if result.returncode != 0:
            return {}
        values = (result.stdout.strip().split("|") + ["", "", ""])[:3]
        env = {}
        for name, value in zip(
            ("http_proxy", "https_proxy", "no_proxy"), values, strict=True
        ):
            if value and name != "no_proxy":
                value = self._resolved(value)
            if value:
                env[name] = env[name.upper()] = value
        return env

    def _resolved(self, url: str) -> str:
        host = urlsplit(url).hostname or ""
        if not host or host.replace(".", "").isdigit():
            return url
        answer = self.call("getent", "hosts", host, check=False).stdout.split()
        return url.replace(host, answer[0], 1) if answer else url

    def login(self, registry: str, user: str, token: str) -> None:
        self.call(
            "docker", "login", registry, "-u", user, "--password-stdin", stdin=token
        )

    def pull(self, image: str) -> bool:
        return self.call("docker", "pull", "-q", image, check=False).returncode == 0

    def image_id(self, image: str) -> str | None:
        result = self.call(
            "docker", "image", "inspect", "-f", "{{.Id}}", image, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def container(self, name: str) -> tuple[bool, str] | None:
        result = self.call(
            "docker",
            "inspect",
            "-f",
            '{{.State.Running}} {{index .Config.Labels "ptk.config"}}',
            name,
            check=False,
        )
        if result.returncode != 0:
            return None
        running, _, label = result.stdout.strip().partition(" ")
        return running == "true", label

    def create(
        self,
        name: str,
        image: str,
        *,
        user: str,
        workdir: str,
        mounts: Sequence[str],
        env: Mapping[str, str],
        labels: Mapping[str, str],
        run_args: Sequence[str],
    ) -> None:
        argv = [
            "docker", "run", "-d", "--name", name, "--init",
            "--add-host", "host.docker.internal:host-gateway",
            "--user", user, "-w", workdir,
        ]  # fmt: skip
        for mount in mounts:
            argv += ["-v", mount]
        for key, value in env.items():
            argv += ["-e", f"{key}={value}"]
        for key, value in labels.items():
            argv += ["--label", f"{key}={value}"]
        argv += [*run_args, "--entrypoint", "sleep", image, "infinity"]
        self.call(*argv)

    def start(self, name: str) -> None:
        self.call("docker", "start", name)

    def ensure_user(self, name: str, user: str, home: str) -> None:
        """Create a passwd entry for the uid:gid the container runs as, if missing."""
        uid, _, gid = user.partition(":")
        script = (
            'getent group "$2" >/dev/null || groupadd -g "$2" "ptk-$2"; '
            'getent passwd "$1" >/dev/null || '
            'useradd -o -u "$1" -g "$2" -M -d "$3" -s /bin/bash "ptk-$1"'
        )
        self.call(
            "docker", "exec", "-u", "0", name, "sh", "-c", script, "sh", uid, gid, home
        )

    def processes(self, name: str) -> int:
        result = self.call("docker", "top", name, check=False)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return max(len(lines) - 1, 0) if result.returncode == 0 else 0

    def restart(self, name: str) -> None:
        self.call("docker", "restart", "-t", "10", name)

    def stop(self, name: str) -> bool:
        return self.call("docker", "stop", name, check=False).returncode == 0

    def remove(self, name: str) -> bool:
        return self.call("docker", "rm", "-f", name, check=False).returncode == 0

    def containers(self, label: str) -> list[list[str]]:
        result = self.call(
            "docker", "ps", "-a", "--filter", f"label={label}",
            "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}", check=False,
        )  # fmt: skip
        return [line.split("\t") for line in result.stdout.splitlines() if line.strip()]

    def exec(
        self,
        name: str,
        argv: Sequence[str],
        *,
        workdir: str,
        values: Mapping[str, str],
    ) -> int:
        command = ["docker", "exec", "-w", workdir]
        if self._interactive:
            command.append("-it")
        for key in values:
            command += ["-e", key]
        return self.call(
            *command, name, *argv, values=values, capture=False, check=False
        ).returncode

    def rsync(self, *args: str) -> int:
        return self.call("rsync", *args, capture=False, check=False).returncode
