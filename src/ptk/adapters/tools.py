"""ToolInstaller adapter: Chocolatey, uv tool, verified downloads, apt/dnf.

* Chocolatey needs an administrator shell; without one ptk explains what to do.
  Bootstrapping Chocolatey itself only happens on explicit request.
* Downloads are verified (sha256) and unpacked into the user's tool folder:
  ``%LOCALAPPDATA%\\ptk\\tools\\<name>`` or ``~/.local/share/ptk/tools/<name>``
  (``PTK_TOOLS_DIR`` overrides). Their ``bin`` folders go first on PATH for
  every command ptk runs.
* apt/dnf use ``sudo -n`` (no password prompt hidden behind a running command).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path

from ..application.ports import ProcessRunner
from ..domain.errors import PtkError
from ..domain.execution.model import CommandSpec
from ..domain.tools import InstallMethod

WINDOWS = sys.platform.startswith("win")
MARKER = ".ptk-tool.json"
CHOCO_BOOTSTRAP = (
    "Set-ExecutionPolicy Bypass -Scope Process -Force; "
    "[System.Net.ServicePointManager]::SecurityProtocol = "
    "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
    "iex ((New-Object System.Net.WebClient).DownloadString("
    "'https://community.chocolatey.org/install.ps1'))"
)


def default_tools_dir(environ: Mapping[str, str]) -> Path:
    if environ.get("PTK_TOOLS_DIR"):
        return Path(environ["PTK_TOOLS_DIR"])
    if WINDOWS:
        return (
            Path(environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            / "ptk"
            / "tools"
        )
    base = environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "ptk" / "tools"


def is_admin() -> bool:
    if not WINDOWS:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


class SystemToolInstaller:
    def __init__(
        self,
        runner: ProcessRunner,
        environ: Mapping[str, str],
        *,
        uv: str = "uv",
        tools_dir: Path | None = None,
        admin: Callable[[], bool] = is_admin,
        windows: bool = WINDOWS,
    ):
        self._runner = runner
        self._environ = dict(environ)
        self._uv = uv
        self.tools_dir = tools_dir or default_tools_dir(environ)
        self._admin = admin
        self._windows = windows
        self._uv_bin: str | None = None

    # -- PATH ---------------------------------------------------------------------------

    def bin_dirs(self) -> list[str]:
        dirs: list[str] = []
        if self.tools_dir.is_dir():
            for marker in sorted(self.tools_dir.glob(f"*/{MARKER}")):
                try:
                    data = json.loads(marker.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                dirs.append(str(marker.parent / data.get("bin", "")))
        uv_bin = self._uv_tool_bin()
        if uv_bin:
            dirs.append(uv_bin)
        return dirs

    def _uv_tool_bin(self) -> str | None:
        if self._uv_bin is None:
            lines: list[str] = []
            outcome = self._runner.run(
                CommandSpec(
                    argv=[self._uv, "tool", "dir", "--bin"],
                    env=self._environ,
                    timeout=20,
                ),
                lines.append,
            )
            self._uv_bin = lines[-1].strip() if outcome.exit_code == 0 and lines else ""
        return self._uv_bin or None

    # -- install ------------------------------------------------------------------------

    def install(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None:
        handler = {
            "choco": self._choco,
            "uv_tool": self._uv_tool,
            "download": self._download,
            "apt": self._system,
            "dnf": self._system,
        }[method.kind]
        handler(name, method, out)

    def _run(
        self,
        argv: list[str],
        out: Callable[[str], None],
        what: str,
        timeout: float = 1800,
    ) -> None:
        outcome = self._runner.run(
            CommandSpec(argv=argv, env=self._environ, timeout=timeout), out
        )
        if outcome.exit_code != 0:
            raise PtkError(
                f"{what} failed ({outcome.error or f'exit code {outcome.exit_code}'})"
            )

    def _choco(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None:
        if not shutil.which("choco", path=self._environ.get("PATH")):
            raise PtkError(
                "Chocolatey is not installed - run 'ptk setup install --bootstrap-choco' in an "
                "administrator terminal, or install the tool another way"
            )
        if not self._admin():
            raise PtkError(
                f"Chocolatey needs an administrator terminal: open one and run "
                f"'ptk setup install' again (or: {method.describe()} -y)"
            )
        argv = ["choco", "install", method.package, "-y", "--no-progress"]
        if method.version:
            argv += ["--version", method.version, "--allow-downgrade"]
        self._run(argv, out, "choco install")

    def bootstrap_choco(self, out: Callable[[str], None]) -> None:
        if not self._windows:
            raise PtkError("Chocolatey is only available on Windows")
        if shutil.which("choco", path=self._environ.get("PATH")):
            out("Chocolatey is already installed")
            return
        if not self._admin():
            raise PtkError("installing Chocolatey needs an administrator terminal")
        self._run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                CHOCO_BOOTSTRAP,
            ],
            out,
            "Chocolatey installation",
        )

    def _uv_tool(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None:
        self._run(
            [self._uv, "tool", "install", "--force", method.package],
            out,
            "uv tool install",
        )
        self._uv_bin = None  # may have been created just now

    def _system(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None:
        manager = "apt-get" if method.kind == "apt" else "dnf"
        prefix = [] if is_admin() else ["sudo", "-n"]
        try:
            self._run(
                [*prefix, manager, "install", "-y", method.package],
                out,
                f"{manager} install",
            )
        except PtkError as exc:
            raise PtkError(
                f"{exc} - run 'sudo {manager} install -y {method.package}' yourself"
            ) from None

    def _download(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None:
        source = method.download
        assert source is not None
        target = self.tools_dir / name
        with tempfile.TemporaryDirectory(prefix="ptk-download-") as tmp:
            file = Path(tmp) / (source.url.rsplit("/", 1)[-1] or "download")
            out(f"downloading {source.url}")
            try:
                with (
                    urllib.request.urlopen(source.url, timeout=120) as response,
                    file.open("wb") as handle,
                ):
                    shutil.copyfileobj(response, handle)
            except OSError as exc:
                raise PtkError(f"download failed: {exc}") from None
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if source.sha256:
                if digest.lower() != source.sha256.lower():
                    raise PtkError(f"sha256 mismatch for {source.url}: got {digest}")
            else:
                out(f"warning: no sha256 configured for {name} (got {digest})")
            staging = Path(tmp) / "unpacked"
            staging.mkdir()
            if source.extract and zipfile.is_zipfile(file):
                _unzip(file, staging)
            elif source.extract and tarfile.is_tarfile(file):
                with tarfile.open(file) as archive:
                    archive.extractall(staging, filter="data")
            else:
                shutil.copy2(file, staging / file.name)
                (staging / file.name).chmod(0o755)
            entries = list(staging.iterdir())
            root = entries[0] if len(entries) == 1 and entries[0].is_dir() else staging
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(root), target)
        (target / MARKER).write_text(
            json.dumps({"url": source.url, "sha256": digest, "bin": source.bin or ""}),
            encoding="utf-8",
        )
        out(f"installed {name} into {target}")


def _unzip(file: Path, target: Path) -> None:
    with zipfile.ZipFile(file) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise PtkError(f"unsafe path in archive: {member.filename}")
        archive.extractall(target)
        for member in archive.infolist():  # zip does not restore permissions by itself
            mode = (member.external_attr >> 16) & 0o777
            if mode:
                (target / member.filename).chmod(mode)
