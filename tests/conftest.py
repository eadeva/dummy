from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from ptk.adapters.host import SystemHost
from ptk.bootstrap import create_app

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


def grant_maintainer(root: Path) -> None:
    """Explicitly authorize the test runner in a temporary project's real list."""
    main = root / ".main.ptk.yml"
    data = yaml.safe_load(main.read_text()) if main.exists() else {}
    folder = root / data.get("repository", {}).get("config_path", ".")
    (folder / "maintainers.ptk.yml").write_text(
        yaml.safe_dump({"maintainers": [SystemHost().user_id()]}), encoding="utf-8"
    )


@pytest.fixture
def write(tmp_path: Path):
    """write({".main.ptk.yml": "...", "a/b.ptk.yml": "..."}) -> project root."""

    def _write(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            text = textwrap.dedent(text).lstrip("\n")
            if target.name == ".main.ptk.yml" and "repository:" not in text:
                text = text.rstrip() + "\nrepository: {alias: demo, config_path: .}\n"
            target.write_text(text, encoding="utf-8")
        return tmp_path

    return _write


@pytest.fixture
def load():
    """load(root, **kwargs) -> Project, with a clean host environment (no CI)."""

    def _load(root: Path, environ: dict[str, str] | None = None, **kwargs):
        app = create_app(environ=environ or {})
        if root == DEMO:
            kwargs.setdefault("config_file", DEMO / ".main.ptk.yml")
        return app.load_project.execute(root, **kwargs)

    return _load


MINIMAL = """
project: {name: demo}
jobs:
  build:
    steps:
      - compile: "make all"
"""
