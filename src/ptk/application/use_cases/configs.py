"""Shared base configs with project overlays (use case ``SharedConfigs``).

Only the configs listed under ``configs:`` are managed. The effective files
are committed; ``ptk configs check`` keeps them in sync in CI.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ...domain import shared_configs as sc
from ...domain.errors import PtkError
from ...domain.suggest import did_you_mean
from ..ports import SharedConfigFiles
from .project import Project

RUFF_EXTEND = 'extend = "{base}"'


@dataclass
class ConfigFile:
    name: str
    path: Path
    new_text: str
    old_text: str | None
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.old_text is None:
            return "new"
        return "up to date" if self.old_text == self.new_text else "out of date"

    def diff(self, root: Path) -> str:
        rel = (
            self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        )
        return "".join(
            difflib.unified_diff(
                (self.old_text or "").splitlines(keepends=True),
                self.new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )


class SharedConfigs:
    def __init__(self, files: SharedConfigFiles):
        self._files = files

    def plan(
        self, project: Project, names: list[str] | None = None
    ) -> list[ConfigFile]:
        configured = {n: s for n, s in project.config.configs.items() if s.enabled}
        for name in names or []:
            if name not in configured:
                known = list(project.config.configs) or list(sc.CONFIG_FILES)
                raise PtkError(
                    f"config '{name}' is not managed by this project{did_you_mean(name, known)}"
                    " (list it under 'configs:' in main.ptk.yml)"
                )
        result = []
        for name, spec in configured.items():
            if names and name not in names:
                continue
            output = project.root / (spec.output or sc.CONFIG_FILES[name])
            if name == "ruff":
                result += self._ruff(project, output)
                continue
            base_text, version = self._files.base(name)
            data = self._files.parse(base_text, f"ptk base {name}")
            if spec.overlay:
                overlay_path = project.root / spec.overlay
                overlay_text = self._files.read(overlay_path)
                if overlay_text is None:
                    raise PtkError(
                        f"configs.{name}.overlay: file not found: {spec.overlay}"
                    )
                overlay = self._files.parse(overlay_text, spec.overlay) or {}
                data = sc.MERGERS[name](data, overlay)
            text = sc.header(name, version, spec.overlay) + self._files.render(
                name, data
            )
            result.append(ConfigFile(name, output, text, self._files.read(output)))
        return result

    def sync(
        self, project: Project, names: list[str] | None = None
    ) -> list[ConfigFile]:
        planned = self.plan(project, names)
        for item in planned:
            if item.status != "up to date":
                self._files.write(item.path, item.new_text)
        return planned

    # -- ruff: native 'extend', the project's ruff.toml is the overlay --------------------

    def _ruff(self, project: Project, base_path: Path) -> list[ConfigFile]:
        base_text, version = self._files.base("ruff")
        text = sc.header("ruff", version, "ruff.toml") + _strip_base_header(base_text)
        items = [ConfigFile("ruff", base_path, text, self._files.read(base_path))]
        rel = base_path.relative_to(project.root).as_posix()
        own = project.root / "ruff.toml"
        own_text = self._files.read(own)
        pyproject = self._files.read(project.root / "pyproject.toml") or ""
        line = RUFF_EXTEND.format(base=rel)
        if own_text is None and "[tool.ruff" not in pyproject:
            starter = (
                "# Project ruff settings - extends ptk's base (ruff defaults + I, B, UP, SIM)\n"
                f"{line}\n"
            )
            items.append(ConfigFile("ruff", own, starter, None))
        elif own_text is not None and not re.search(
            r"^\s*extend\s*=", own_text, re.MULTILINE
        ):
            items[0].notes.append(f"add {line} at the top of ruff.toml")
        elif (
            own_text is None
            and "extend" not in pyproject.split("[tool.ruff", 1)[1][:400]
        ):
            items[0].notes.append(f"add {line} under [tool.ruff] in pyproject.toml")
        return items


def _strip_base_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    while lines and lines[0].startswith("# ptk-base:"):
        lines.pop(0)
    return "".join(lines)
