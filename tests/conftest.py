from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ptk.bootstrap import create_app

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


@pytest.fixture
def write(tmp_path: Path):
    """write({"main.ptk.yml": "...", "a/b.ptk.yml": "..."}) -> project root."""
    def _write(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
        return tmp_path
    return _write


@pytest.fixture
def load():
    """load(root, **kwargs) -> Project, with a clean host environment (no CI)."""
    def _load(root: Path, environ: dict[str, str] | None = None, **kwargs):
        app = create_app(environ=environ or {})
        return app.load_project.execute(root, **kwargs)
    return _load


MINIMAL = """
project: {name: demo}
actions:
  build:
    steps:
      - compile: "make all"
"""
