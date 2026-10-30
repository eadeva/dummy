"""Bundled and development VSIX installation, without changing real VS Code."""

import json
import subprocess
import zipfile
from contextlib import contextmanager

import pytest
from click.testing import CliRunner

from ptk.drivers.cli import extension
from ptk.drivers.cli.main import cli
from ptk.extension_bundle import EXTENSION_ID, inspect_vsix


@pytest.fixture
def vsix(tmp_path):
    path = tmp_path / "extension with spaces.vsix"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "extension/package.json",
            json.dumps(
                {
                    "publisher": "eadeva",
                    "name": "project-toolkit",
                    "version": "0.7.0",
                    "main": "./dist/extension.js",
                }
            ),
        )
        archive.writestr("extension/dist/extension.js", "// bundled extension")
        archive.writestr("extension.vsixmanifest", "<PackageManifest/>")
    return path


@pytest.fixture
def runner(tmp_path, monkeypatch, vsix):
    monkeypatch.chdir(tmp_path)

    @contextmanager
    def bundled():
        yield vsix

    def forbidden(*args, **kwargs):
        raise AssertionError("host extension setup must not load a project")

    monkeypatch.setattr(extension, "bundled_vsix", bundled)
    monkeypatch.setattr(
        "ptk.application.use_cases.project.LoadProject.execute", forbidden
    )
    return CliRunner()


@pytest.mark.parametrize("configuration", [None, "broken: [", "virtual_monorepo: ["])
def test_export_without_project_loading(runner, tmp_path, vsix, configuration):
    if configuration:
        (tmp_path / ".main.ptk.yml").write_text(configuration)
    target = tmp_path / "export.vsix"
    result = runner.invoke(cli, ["self-service", "extension", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == vsix.read_bytes()
    assert inspect_vsix(target)["version"] == "0.7.0"
    # Never overwrite a manually supplied file, even with identical content.
    result = runner.invoke(cli, ["self-service", "extension", "--output", str(target)])
    assert result.exit_code != 0
    assert target.read_bytes() == vsix.read_bytes()


@pytest.mark.parametrize(
    "installed,force,changes",
    [
        (None, False, True),
        ("0.6.0", False, True),
        ("0.7.0", False, False),
        ("0.8.0", False, False),
        ("0.7.0", True, True),
        ("0.8.0", True, True),
    ],
)
def test_version_policy_and_profile(
    runner, monkeypatch, vsix, installed, force, changes
):
    calls = []
    current = installed
    monkeypatch.setattr(
        extension.shutil, "which", lambda name: "/code with spaces/code"
    )

    def execute(argv, **kwargs):
        nonlocal current
        calls.append(argv)
        assert kwargs["check"] is False
        assert argv[0] == "/code with spaces/code"
        assert argv[-2:] == ["--profile", "Development profile"]
        if "--install-extension" in argv:
            assert argv[2] == str(vsix) and "--force" in argv
            current = "0.7.0"
        return subprocess.CompletedProcess(
            argv, 0, f"{EXTENSION_ID}@{current}\n" if current else "", ""
        )

    monkeypatch.setattr(extension.subprocess, "run", execute)
    args = ["self-service", "extension", "--profile", "Development profile"]
    result = runner.invoke(cli, args + (["--force"] if force else []))
    assert result.exit_code == 0, result.output
    assert any("--install-extension" in call for call in calls) == changes
    assert ("Installed" if changes else "Keeping") in result.output


def test_missing_editor_can_be_skipped(runner, monkeypatch):
    monkeypatch.setattr(extension.shutil, "which", lambda name: None)
    result = runner.invoke(cli, ["self-service", "extension"])
    assert result.exit_code != 0 and "not found" in result.output
    result = runner.invoke(cli, ["self-service", "extension", "--if-available"])
    assert result.exit_code == 0 and "Skipping" in result.output


@pytest.mark.parametrize("mode", ["error", "timeout", "not-installed"])
def test_installation_failures_are_not_reported_as_success(runner, monkeypatch, mode):
    monkeypatch.setattr(extension.shutil, "which", lambda name: "/code")

    def execute(argv, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired(argv, 120)
        return subprocess.CompletedProcess(
            argv,
            3 if mode == "error" else 0,
            "",
            "editor failure" if mode == "error" else "",
        )

    monkeypatch.setattr(extension.subprocess, "run", execute)
    result = runner.invoke(cli, ["self-service", "extension"])
    assert result.exit_code != 0
    assert "Installed Project Toolkit" not in result.output


def test_development_vsix_and_missing_bundle(tmp_path, monkeypatch, vsix):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extension, "files", lambda package: tmp_path)
    runner = CliRunner()
    target = tmp_path / "export.vsix"
    result = runner.invoke(cli, ["self-service", "extension", "--output", str(target)])
    assert result.exit_code != 0 and "editable/source" in result.output
    result = runner.invoke(
        cli, ["self-service", "extension", "--vsix", str(vsix), "--output", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == vsix.read_bytes()


def test_invalid_vsix_and_export_options(runner, tmp_path):
    path = tmp_path / "broken.vsix"
    path.write_bytes(b"not a zip file")
    result = runner.invoke(
        cli,
        [
            "self-service",
            "extension",
            "--vsix",
            str(path),
            "--output",
            str(tmp_path / "export.vsix"),
        ],
    )
    assert result.exit_code != 0 and "Invalid" in result.output
    result = runner.invoke(
        cli, ["self-service", "extension", "--output", "export.vsix", "--force"]
    )
    assert result.exit_code == 2
