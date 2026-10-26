"""Toolbase bridge; activation stays local to the selected PTK action."""

from pathlib import Path

from ...domain.config.model import ToolbaseSource
from ...domain.errors import PtkError
from ..locking import file_lock


def root(environ) -> Path:
    value = environ.get("TB_HOMEDIR")
    if not value:
        raise PtkError(
            "Toolbase requires TB_HOMEDIR and installed tbexcmd/TBUpdate commands"
        )
    return Path(value).resolve()


def bin_dirs(source: ToolbaseSource, environ) -> list[str]:
    folder = root(environ) / source.package / source.version
    result = []
    for entry in source.bin:
        binary = (folder / entry).resolve()
        if not binary.is_relative_to(folder.resolve()):
            raise PtkError(
                "Toolbase bin paths must stay inside the selected tool version"
            )
        if binary.is_dir():
            result.append(str(binary))
    return result


def install(source: ToolbaseSource, environ, run, out, lock: Path) -> None:
    folder = root(environ) / source.package / source.version
    # Toolbase changes shared state; serialize enable and update across tools/repos.
    with file_lock(lock, timeout=1800):
        if not folder.is_dir():
            run(
                [
                    "tbexcmd",
                    f"-useEnv:{source.environment}",
                    "-command",
                    "EnableTool",
                    f"{source.package}/{source.version}",
                ],
                out,
                "Toolbase enable",
            )
            run(["TBUpdate", "-e"], out, "Toolbase update")
        if len(bin_dirs(source, environ)) != len(source.bin) or not folder.is_dir():
            raise PtkError(
                f"Toolbase did not create the configured tool directories: {folder}"
            )
    out(f"Toolbase {source.package}/{source.version} is available")
