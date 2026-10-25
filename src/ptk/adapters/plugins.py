"""Explicit distribution allow-list for installed PTK entry points."""

import re
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

from ..domain.errors import PtkError

GROUPS = (
    "steps",
    "reporters",
    "report_contributors",
    "installers",
    "secret_providers",
    "generators",
)
RESERVED = {
    "steps": {
        "echo",
        "wait",
        "report.import",
        "configs.sync",
        "tools.ensure",
        "files.copy",
        "files.clean",
        "variant.generate",
    },
    "reporters": {"json", "junit", "html", "markdown", "github"},
    "secret_providers": {"env", "keyring", "gopass", "vault", "prompt"},
    "generators": {"header", "cmake", "bazel", "make", "yocto", "robot", "sphinx"},
}


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class Plugins:
    groups: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {g: {} for g in GROUPS}
    )

    def __getitem__(self, group):
        return self.groups[group]


def load_plugins(packages: list[str]) -> Plugins:
    result = Plugins()
    wanted = {normalized(p) for p in packages}
    if not wanted:
        return result
    found = set()
    for group in GROUPS:
        for entry in entry_points(group=f"ptk.{group}"):
            dist = normalized(entry.dist.metadata["Name"]) if entry.dist else ""
            if dist not in wanted:
                continue
            found.add(dist)
            if entry.name in result[group] or entry.name in RESERVED.get(group, set()):
                raise PtkError(f"plugin collision: ptk.{group}:{entry.name}")
            try:
                handler = entry.load()
            except Exception as exc:  # noqa: BLE001 - annotate third-party import failures
                raise PtkError(
                    f"cannot load plugin {dist}/{entry.name}: {exc}"
                ) from None
            if not callable(handler):
                raise PtkError(f"plugin {dist}/{entry.name} must be callable")
            result[group][entry.name] = handler
    missing = wanted - found
    if missing:
        raise PtkError(
            f"no PTK entry points found for installed package(s): {', '.join(sorted(missing))}"
        )
    return result


class PluginInstaller:
    def __init__(self, base, handlers):
        self.base = base
        self.handlers = handlers

    def bin_dirs(self, tools=None):
        return self.base.bin_dirs(tools)

    def clean_environment(self, env):
        return self.base.clean_environment(env)

    def install(self, name, method, out):
        if method.kind.startswith("plugin:"):
            key = method.kind.removeprefix("plugin:")
            if key not in self.handlers:
                raise PtkError(f"installer plugin '{key}' is not enabled")
            self.handlers[key](name, method.options, out)
        else:
            self.base.install(name, method, out)
