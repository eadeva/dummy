"""Environment of a command (pure).

Every command gets its own environment dictionary; the ptk process itself is
never modified. Layers, later ones win:

1. host environment - or, with ``environment.isolate``, only the OS essentials
   plus ``environment.keep``
2. ``environment.set`` / ``unset`` / ``path_prepend`` / ``path_append``
3. generated variables: ``PTK_*`` (run), ``PTK_PARAM_*``, ``VARIANT_*`` (variant)
4. job ``env``
5. step ``env`` (and, later, the step's secrets)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

WINDOWS_ESSENTIAL = {
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "COMPUTERNAME",
    "USERNAME",
    "USERDOMAIN",
    "OS",
    "PATHEXT",
    "COMSPEC",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PROGRAMDATA",
    "APPDATA",
    "LOCALAPPDATA",
    "COMMONPROGRAMFILES",
    "PUBLIC",
    "PSMODULEPATH",
}
POSIX_ESSENTIAL = {
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "TZ",
}


def _find_key(env: Mapping[str, str], name: str, windows: bool) -> str | None:
    if name in env:
        return name
    if windows:
        for key in env:
            if key.upper() == name.upper():
                return key
    return None


def base_environment(
    host: Mapping[str, str],
    *,
    os_name: str,
    isolate: bool,
    keep: Iterable[str],
    set_: Mapping[str, str],
    unset: Iterable[str],
    path_prepend: Iterable[str],
    path_append: Iterable[str],
    inherit_path: bool = True,
) -> dict[str, str]:
    windows = os_name == "windows"
    sep = ";" if windows else ":"
    if not inherit_path:
        host = {k: v for k, v in host.items() if k.upper() != "PATH"}
        system_root = next(
            (v for k, v in host.items() if k.upper() == "SYSTEMROOT"), r"C:\Windows"
        )
        host = {
            **host,
            "PATH": (system_root + r"\System32;" + system_root)
            if windows
            else "/usr/bin:/bin",
        }
    if isolate:
        essentials = WINDOWS_ESSENTIAL if windows else POSIX_ESSENTIAL
        wanted = {n.upper() if windows else n for n in (*essentials, *keep, "PATH")}
        env = {k: v for k, v in host.items() if (k.upper() if windows else k) in wanted}
    else:
        env = dict(host)
    for name in unset:
        key = _find_key(env, name, windows)
        if key:
            del env[key]
    for name, value in set_.items():
        # Windows environment names are case-insensitive, including Path/PATH.
        key = _find_key(env, name, windows) or name
        env[key] = value
    path_key = _find_key(env, "PATH", windows) or "PATH"
    parts = [p for p in env.get(path_key, "").split(sep) if p]
    parts = [*path_prepend, *parts, *path_append]
    if parts:
        env[path_key] = sep.join(dict.fromkeys(parts))
    return env


def prepend_path(
    env: dict[str, str], directory: str, *, os_name: str
) -> dict[str, str]:
    windows = os_name == "windows"
    key = _find_key(env, "PATH", windows) or "PATH"
    sep = ";" if windows else ":"
    current = env.get(key, "")
    env = dict(env)
    env[key] = directory + (sep + current if current else "")
    return env


def param_variables(params: Mapping[str, object]) -> dict[str, str]:
    from ..config.substitution import to_text

    return {
        f"PTK_PARAM_{name.upper()}": to_text(value) for name, value in params.items()
    }
