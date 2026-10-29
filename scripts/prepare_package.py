"""Build, validate and stage PTK release artifacts locally. No upload operation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

from ptk.package_version import package_version

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run([sys.executable, *args], cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owned_output(output: Path) -> None:
    """Only replace this job's unmodified previous output, never arbitrary files."""
    if output.is_symlink() or output.is_junction():
        raise ValueError(f"refusing linked output directory: {output}")
    if not output.exists():
        return
    if not output.is_dir():
        raise ValueError(f"output is not a directory: {output}")
    entries = list(output.rglob("*"))
    if not entries:
        return
    if any(path.is_symlink() or path.is_junction() for path in entries):
        raise ValueError("refusing linked files in previous package output")
    manifest = output / "manifest.json"
    if not manifest.is_file():
        raise ValueError(f"refusing to replace unowned output: {output}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    expected = data.get("files", {})
    actual = {
        path.relative_to(output).as_posix(): sha256(path)
        for path in entries
        if path.is_file() and path != manifest
    }
    if data.get("prepared_by") != "ptk package" or actual != expected:
        raise ValueError(
            f"previous package output contains changed or additional files: {output}"
        )


SMOKE = """
import sys
from pathlib import Path
from importlib.metadata import distribution
target = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
import ptk
assert Path(ptk.__file__).resolve().is_relative_to(target), ptk.__file__
assert ptk.__version__ == distribution('ptk').version
entry = next(e for e in distribution('ptk').entry_points if e.group == 'console_scripts' and e.name == 'ptk')
sys.argv = ['ptk', *sys.argv[2:]]
entry.load()()
"""


def check_skill_links(project: Path) -> None:
    # Windows temporary paths can contain short names or redirected ancestors.
    # Compare canonical paths on both sides of the containment check.
    github = (project / ".github").resolve()
    for skill in (github / "skills").glob("*/SKILL.md"):
        for link in re.findall(r"\]\(([^)]+)\)", skill.read_text(encoding="utf-8")):
            target = (skill.parent / link).resolve()
            if not target.is_relative_to(github) or not target.exists():
                raise ValueError(
                    f"broken installed skill reference: {skill.name}: {link}"
                )


def smoke(wheel: Path, temporary: Path) -> None:
    installed = temporary / "installed"
    run(
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--no-warn-script-location",
        "--target",
        str(installed),
        str(wheel),
    )
    project = temporary / "consumer"
    project.mkdir()
    # Export before project initialization: self-service extension is host-level and the
    # wheel must carry the VSIX without Node.js or access to the source checkout.
    exported = temporary / "bundled-extension.vsix"
    run(
        "-I",
        "-c",
        SMOKE,
        str(installed),
        "self-service",
        "extension",
        "--output",
        str(exported),
        cwd=project,
    )
    with zipfile.ZipFile(exported) as archive:
        archive.getinfo("extension/package.json")
        archive.getinfo("extension/dist/extension.js")
    for args in (
        ["init", "--config-dir", "config/ptk", "--yes"],
        ["validate"],
        ["maintainer", "sync", "tasks"],
        ["maintainer", "sync", "skills"],
        ["maintainer", "sync", "skills", "--check"],
    ):
        run("-I", "-c", SMOKE, str(installed), *args, cwd=project)
    assert (project / ".github/skills/ptk-config-authoring/SKILL.md").is_file()
    assert (project / ".github/ptk/docs/configuration.rst").is_file()
    check_skill_links(project)


def prepare(output: Path) -> Path:
    output = output.absolute()
    if ROOT.is_relative_to(output.resolve()):
        raise ValueError(
            "package output must not replace the source repository or its ancestors"
        )
    owned_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    version = package_version(ROOT, resolved_version=os.environ.get("PTK_VERSION_PTK"))
    with tempfile.TemporaryDirectory(prefix=".ptk-package-", dir=output.parent) as work:
        temporary = Path(work)
        staged = temporary / "release"
        dist = staged / "dist"
        dist.mkdir(parents=True)
        # uv supplied the declared release dependencies. Build still creates the
        # wheel from the sdist, checking that all build inputs survived packaging.
        run(
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
            env={**os.environ, "_PTK_BUILD_VERSION": version},
        )
        wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise ValueError("expected exactly one wheel and one source distribution")
        with zipfile.ZipFile(wheels[0]) as wheel:
            wheel.getinfo("ptk/resources/extension/project-toolkit.vsix")
            metadata = Parser().parsestr(
                wheel.read(
                    next(
                        name
                        for name in wheel.namelist()
                        if name.endswith(".dist-info/METADATA")
                    )
                ).decode()
            )
            if metadata["Name"] != project["name"] or metadata["Version"] != version:
                raise ValueError(
                    "distribution metadata differs from the PTK project/version"
                )
            for name in (
                "skills/ptk-config-authoring/SKILL.md",
                "docs/configuration.rst",
                "examples/plugin/pyproject.toml",
            ):
                wheel.getinfo("ptk/resources/authoring/" + name)
        run("-m", "twine", "check", "--strict", str(wheels[0]), str(sdists[0]))
        with tempfile.TemporaryDirectory(prefix="ptk-wheel-smoke-") as consumer:
            smoke(wheels[0], Path(consumer))
        html = temporary / "html"
        run("-m", "sphinx", "-W", "--keep-going", "-b", "html", "docs", str(html))
        docs = staged / "docs" / f"ptk-{version}-docs.zip"
        docs.parent.mkdir()
        with zipfile.ZipFile(docs, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(html.rglob("*")):
                if path.is_file() and ".doctrees" not in path.relative_to(html).parts:
                    archive.write(path, path.relative_to(html).as_posix())
        checksums = {
            path.relative_to(staged).as_posix(): sha256(path)
            for path in sorted(staged.rglob("*"))
            if path.is_file()
        }
        sums = staged / "SHA256SUMS"
        sums.write_text(
            "".join(f"{value}  {name}\n" for name, value in checksums.items()),
            encoding="utf-8",
        )
        checksums[sums.name] = sha256(sums)
        (staged / "manifest.json").write_text(
            json.dumps(
                {
                    "prepared_by": "ptk package",
                    "package": project["name"],
                    "version": version,
                    "files": checksums,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        # Keep a prior successful preparation until every check has passed.
        owned_output(output)
        backup = temporary / "previous"
        if output.exists():
            output.rename(backup)
        try:
            staged.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        destination = prepare(args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Package preparation failed: {exc}\n")
    print(f"Prepared and validated {destination}; nothing was published.")
