"""Build and inspect the bundled VSIX. Stdlib-only for use by Hatch."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

RESOURCE = "resources/extension/project-toolkit.vsix"
EXTENSION_ID = "eadeva.project-toolkit"


def inspect_vsix(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as archive:
            package = json.loads(archive.read("extension/package.json"))
            identity = f"{package['publisher']}.{package['name']}"
            version = package["version"]
            if identity != EXTENSION_ID or not isinstance(version, str):
                raise ValueError("unexpected extension identity or version")
            main = package["main"].removeprefix("./")
            archive.getinfo("extension/" + main)
            archive.getinfo("extension.vsixmanifest")
            return package
    except (KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid Project Toolkit VSIX: {path}: {exc}") from exc


def build_vsix(root: Path, output: Path) -> None:
    """Compile/test from a checkout; source distributions already contain a VSIX."""
    npm = shutil.which("npm")
    if npm is None:
        raise ValueError(
            "Building PTK from a checkout requires Node.js 22+ and npm for the "
            "bundled extension. Install a released wheel/sdist, or use 'uv sync' "
            "for editable Python development."
        )
    directory = root / "extensions/project-toolkit"
    for args in (
        ["ci", "--include=dev", "--no-audit", "--no-fund"],
        ["run", "package", "--", "--out", str(output)],
    ):
        subprocess.run([npm, *args], cwd=directory, check=True)
    inspect_vsix(output)
