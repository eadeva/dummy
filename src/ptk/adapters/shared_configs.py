"""SharedConfigFiles adapter: base configs from the package, YAML in/out, files."""

from __future__ import annotations

import os
import re
from importlib import resources
from pathlib import Path

import yaml

from ..domain.errors import PtkError

BASES = {
    "pre-commit": "pre-commit.yaml",
    "ruff": "ruff.toml",
    "clang-format": "clang-format.yaml",
    "clang-tidy": "clang-tidy.yaml",
    "clangd": "clangd.yaml",
}


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


class PackageConfigFiles:
    def base(self, name: str) -> tuple[str, str]:
        text = (
            resources.files("ptk.resources.configs")
            .joinpath(BASES[name])
            .read_text("utf-8")
        )
        match = re.match(r"#\s*ptk-base:\s*\S+\s+(\S+)", text)
        return text, match.group(1) if match else "v0"

    def parse(self, text: str, source: str) -> dict:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PtkError(f"{source}: invalid YAML ({exc})") from None
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise PtkError(f"{source}: expected a mapping at the top level")
        return data

    def render(self, name: str, data: dict) -> str:
        text = yaml.dump(
            data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100
        )
        if name in ("clang-format", "clang-tidy", "clangd"):
            text = "---\n" + text
        return text

    def read(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
