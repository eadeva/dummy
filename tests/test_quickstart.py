"""Exercise the documented example on Linux and Windows without external tools."""

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.drivers.cli.main import cli

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "quickstart"


@pytest.mark.parametrize("variant", ["debug", "release"])
def test_quickstart(tmp_path, variant):
    root = tmp_path / "project with spaces"
    shutil.copytree(EXAMPLE, root)
    base = ["-C", str(root / ".main.ptk.yml")]
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    preview = runner.invoke(cli, [*base, "-V", variant, "dry-run", "build"])
    assert preview.exit_code == 0, preview.output
    assert not (root / "_bin").exists()
    message = "Hello with spaces & punctuation"
    run = runner.invoke(cli, [*base, "-V", variant, "build", "--message", message])
    assert run.exit_code == 0, run.output
    assert (root / "_bin" / variant / "build" / "message.txt").read_text() == message
    folder = root / "_reports" / variant / "build"
    report = json.loads((folder / "report.json").read_text())
    assert report["status"] == "passed"
    assert report["totals"]["tests"] == {"passed": 1}
    extra = next(s for s in report["steps"] if s["label"] == "checks/extra")
    assert extra["status"] == ("passed" if variant == "debug" else "skipped")
    for suffix in ("html", "xml", "md"):
        assert (folder / f"report.{suffix}").is_file()
