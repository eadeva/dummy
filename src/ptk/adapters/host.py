"""HostEnvironment adapter: environment variables, CI detection, user identity."""

from __future__ import annotations

import getpass
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

CI_VARIABLES = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "TF_BUILD",
    "BUILDKITE",
    "TEAMCITY_VERSION",
)


class SystemHost:
    def __init__(self, environ: Mapping[str, str] | None = None):
        self._environ = dict(os.environ if environ is None else environ)

    @property
    def variables(self) -> Mapping[str, str]:
        return self._environ

    def is_ci(self) -> bool:
        if self._environ.get("PTK_CI", "").lower() in {"1", "true", "yes"}:
            return True
        if self._environ.get("PTK_CI", "").lower() in {"0", "false", "no"}:
            return False
        return any(
            self._environ.get(name, "").lower() not in ("", "0", "false")
            for name in CI_VARIABLES
        )

    def is_docker(self) -> bool:
        override = self._environ.get("PTK_DOCKER", "").lower()
        if override in {"1", "true", "yes"}:
            return True
        if override in {"0", "false", "no"}:
            return False
        if self._environ.get("container", "").lower() == "docker":
            return True
        if Path("/.dockerenv").is_file():
            return True
        for filename in ("/proc/self/cgroup", "/proc/1/cgroup"):
            try:
                content = Path(filename).read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"(?:/docker/|/docker-[0-9a-f]+\.scope)", content):
                return True
        return False

    def os_name(self) -> str:
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"

    def user_id(self) -> str | None:
        if self._environ.get("GITHUB_ACTIONS", "").lower() == "true":
            return (
                self._environ.get("GITHUB_TRIGGERING_ACTOR")
                or self._environ.get("GITHUB_ACTOR")
                or None
            )
        try:
            return getpass.getuser() or None
        except Exception:  # noqa: BLE001 - getuser can raise various errors
            return None
