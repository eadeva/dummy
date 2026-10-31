"""Real tagged builds and Git-free sdist rebuilds; run in release environments."""

import io
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
            "node_modules",
            "*.vsix",
            "local.ptk.yml",
            ".gen.version.ptk.yml",
        ),
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PTK_", "_PTK_")) or k.startswith("PTK_TEST_")
    }

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
    assert not (source / "reference").exists()  # unpublished legacy/reference material
    assert not (source / "docs/old_cli_xc-ce-utils").exists()
    assert (source / "docs/requirements/index.rst").is_file()
    assert (source / "docs/_static/custom.css").is_file()
    assert (source / "install/install.sh").is_file()
    assert (source / "src/ptk/resources/extension/project-toolkit.vsix").is_file()
    assert not (source / "extensions").exists()  # no Node required by sdist consumers
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
        env={**env, "_PTK_BUILD_VERSION": "9.9.9", "PATH": ""},
        check=True,
        capture_output=True,
        text=True,
    )
    assert wheel_version(next(rebuilt.glob("*.whl"))) == "4.5.6"
    with (
        zipfile.ZipFile(next(dist.glob("*.whl"))) as original,
        zipfile.ZipFile(next(rebuilt.glob("*.whl"))) as rebuilt_wheel,
    ):
        for name in (
            "skills/ptk-github-workflows/SKILL.md",
            "skills/ptk-github-workflows/agents/openai.yaml",
            "docs/guides/github-actions.rst",
            "docs/guides/cx-matrix.rst",
            "docs/guides/output-reuse.rst",
            "docs/guides/reports.rst",
        ):
            asset = f"ptk/resources/authoring/{name}"
            assert original.read(asset) == rebuilt_wheel.read(asset)
            from ptk.authoring_bundle import source_files

            assert source_files(source)[name].read_bytes() == original.read(asset)
        resource = "ptk/resources/extension/project-toolkit.vsix"
        assert original.read(resource) == rebuilt_wheel.read(resource)
        with zipfile.ZipFile(io.BytesIO(original.read(resource))) as extension:
            for name in (
                "dagre.min.js",
                "dagre.LICENSE.txt",
                "dagre.min.js.LEGAL.txt",
                "README.txt",
            ):
                assert extension.read(
                    f"extension/media/graph-engine/{name}"
                ) == original.read(f"ptk/adapters/graph_assets/{name}")
            assert extension.read("extension/media/graph-editor.js")
            assert extension.read("extension/media/dependencies.js")
        for name in (
            "dagre.min.js",
            "dagre.LICENSE.txt",
            "dagre.min.js.LEGAL.txt",
            "graph.js",
            "graph.css",
        ):
            resource = f"ptk/adapters/graph_assets/{name}"
            assert original.read(resource) == rebuilt_wheel.read(resource)
            assert (source / "src" / resource).is_file()
        for name in ("report.css", "report.js"):
            resource = f"ptk/adapters/reporting/assets/{name}"
            assert original.read(resource) == rebuilt_wheel.read(resource)
            assert (source / "src" / resource).is_file()
        assert "ptk/adapters/reporting/log_html.py" not in original.namelist()


def test_editable_build_does_not_need_node(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from hatchling.build import build_editable; import sys; build_editable(sys.argv[1])",
            str(tmp_path),
        ],
        cwd=ROOT,
        env={**os.environ, "PATH": ""},
        check=True,
        capture_output=True,
        text=True,
    )
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as archive:
        assert "ptk/resources/extension/project-toolkit.vsix" not in archive.namelist()
