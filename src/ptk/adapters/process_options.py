"""Console-free launches for PTK's captured/background subprocesses."""

import subprocess
import sys

WINDOWS = sys.platform == "win32"


def detached_process_options() -> dict:
    """Detach the console/session without hiding the application's GUI window."""
    if not WINDOWS:
        return {"start_new_session": True}
    return {
        "creationflags": subprocess.DETACHED_PROCESS
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
