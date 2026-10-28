"""Real tagged builds and Git-free sdist rebuilds; run in release environments."""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

pytest.importorskip(
    "build", reason="package integration needs the release dependency group"
)
pytest.importorskip(
    "hatchling", reason="package integration needs the release dependency group"
)
pytest.importorskip("pip", reason="installed-wheel smoke test needs pip")

ROOT = Path(__file__).resolve().parents[1]


def wheel_version(path):
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        return Parser().parsestr(archive.read(name).decode())["Version"]


def test_tagged_build_and_frozen_sdist_rebuild(tmp_path):
    from scripts.prepare_package import smoke

    checkout = tmp_path / "checkout"
    shutil.copytree(
        ROOT,
        checkout,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".ptk",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "_bin",
            "_builds",
            "_logs",
            "_reports",
            "_build",
            "dist",
            "uv.lock",
            "local.ptk.yml",
            ".gen.version.ptk.yml",
        ),
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PTK_", "_PTK_"))}

    def git(*args):
        subprocess.run(
            ["git", *args], cwd=checkout, env=env, check=True, capture_output=True
        )

    git("init", "-q")
    git("config", "user.name", "PTK Test")
    git("config", "user.email", "test@example.invalid")
    git("add", ".")
    git("commit", "-qm", "initial")
    git("tag", "v4.5.6")
    # An unrelated local configuration error must not prevent installing PTK.
    # This reproduces the install.ps1 failure during Hatch metadata generation.
    (checkout / "config/ptk/artifactory_structure.ptk.yml").write_text(
        "artifactory: {}"
    )
    (checkout / "config/ptk/jobs/unfinished.ptk.yml").write_text("steps: [")
    dist = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=checkout,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert wheel_version(next(dist.glob("*.whl"))) == "4.5.6"
    smoke_root = tmp_path / "smoke"
    smoke_root.mkdir()
    smoke(next(dist.glob("*.whl")), smoke_root)

    extracted = tmp_path / "extracted"
    with tarfile.open(next(dist.glob("*.tar.gz"))) as archive:
        archive.extractall(extracted, filter="data")
    source = next(extracted.iterdir())
    assert not (source / ".git").exists()
    assert (source / "install/install.sh").is_file()
    rebuilt = tmp_path / "rebuilt"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(rebuilt),
        ],
        cwd=source,
        env={**env, "_PTK_BUILD_VERSION": "9.9.9"},
        check=True,
        capture_output=True,
        text=True,
    )
    assert wheel_version(next(rebuilt.glob("*.whl"))) == "4.5.6"
