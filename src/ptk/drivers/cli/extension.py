"""Install the extension shipped with this PTK; never load project configuration."""

import shutil
import subprocess
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path

import rich_click as click
from packaging.version import Version

from ...extension_bundle import EXTENSION_ID, RESOURCE, inspect_vsix


@contextmanager
def bundled_vsix():
    resource = files("ptk").joinpath(RESOURCE)
    if not resource.is_file():
        raise ValueError(
            "This editable/source installation has no bundled VSIX. Build it with "
            "'uv run ptk extension', then use 'ptk self-service extension --vsix PATH --force', "
            "or install a PTK wheel."
        )
    with as_file(resource) as path:
        yield path


def _run(code, args):
    result = subprocess.run(
        [code, *args],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "VS Code command failed: " + (result.stderr or result.stdout).strip()
        )
    return result.stdout


def install_vsix(path, *, code, profile, force):
    package = inspect_vsix(path)
    bundled = Version(package["version"])
    scope = ["--profile", profile] if profile else []
    installed = _run(code, ["--list-extensions", "--show-versions", *scope])
    for line in installed.splitlines():
        name, separator, version = line.strip().rpartition("@")
        if separator and name.casefold() == EXTENSION_ID:
            current = Version(version)
            if current >= bundled and not force:
                click.echo(
                    f"Keeping Project Toolkit {current} (bundled: {bundled}). "
                    "Use --force to reinstall or explicitly downgrade."
                )
                return
    _run(code, ["--install-extension", str(path), "--force", *scope])
    # Do not claim success just because the launcher returned zero.
    installed = _run(code, ["--list-extensions", "--show-versions", *scope])
    if f"{EXTENSION_ID}@{package['version']}" not in installed.lower().splitlines():
        raise ValueError("VS Code did not report the requested extension version.")
    click.echo(f"Installed Project Toolkit {bundled}. Reload your VS Code window.")


@click.command("extension")
@click.option(
    "--code",
    default="code",
    show_default=True,
    help="VS Code launcher or absolute path; e.g. code-insiders.",
)
@click.option("--profile", help="Install into this VS Code profile.")
@click.option(
    "--force",
    is_flag=True,
    help="Reinstall the same version or explicitly downgrade the extension.",
)
@click.option(
    "--if-available",
    is_flag=True,
    help="Skip installation when the VS Code launcher is unavailable.",
)
@click.option(
    "--vsix",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Use an explicitly built development VSIX instead of the bundled one.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Export the VSIX for manual installation; do not run VS Code.",
)
def extension_command(code, profile, force, if_available, vsix, output):
    """Install the bundled Project Toolkit extension (no project required).

    Available to every user. This does not generate project tasks or skills.
    """
    if output and (profile or force or if_available or code != "code"):
        raise click.UsageError("--output cannot be combined with installation options.")
    executable = shutil.which(code) if not output else None
    if not output and executable is None:
        message = f"VS Code launcher '{code}' not found. Install VS Code/add it to PATH, then run 'ptk self-service extension'."
        if if_available:
            click.echo("Skipping extension: " + message)
            return
        raise click.ClickException(message)
    try:
        from contextlib import nullcontext

        with nullcontext(vsix.resolve()) if vsix else bundled_vsix() as path:
            inspect_vsix(path)
            if output:
                # Exclusive creation avoids overwriting a user's file.
                with output.open("xb") as target, path.open("rb") as source:
                    shutil.copyfileobj(source, target)
                click.echo(f"Exported extension to {output}")
            else:
                install_vsix(path, code=executable, profile=profile, force=force)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise click.ClickException(str(exc)) from None
