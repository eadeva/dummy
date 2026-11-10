"""Console-free launches for PTk's captured/background subprocesses."""

import subprocess
import sys

WINDOWS = sys.platform == "win32"


def detached_process_options() -> dict:
    """Detach the console/session without hiding the application's GUI window."""
    if not WINDOWS:
        return {"start_new_session": True}
    # A hidden console (not DETACHED_PROCESS) is inherited by console children such
    # as the venv python.exe launcher, which would otherwise open a new window.
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW
        | subprocess.CREATE_NEW_PROCESS_GROUP
    }


def captured_process_options(*, new_group: bool = False) -> dict:
    if not WINDOWS:
        return {"start_new_session": True} if new_group else {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    flags = subprocess.CREATE_NO_WINDOW
    if new_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return {"creationflags": flags, "startupinfo": startup}
