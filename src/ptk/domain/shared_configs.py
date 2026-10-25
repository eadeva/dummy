"""Merge rules for shared base configs and project overlays (pure).

* generic (clang-format, clangd): mappings merge deeply, everything else is
  replaced; ``null`` in the overlay deletes a key
* clang-tidy: ``Checks``/``WarningsAsErrors`` are combined - an overlay entry
  ``-x`` drops ``x`` from the base and disables it; ``CheckOptions`` merge by key
* pre-commit: repos merge by URL (``rev`` and settings from the overlay), hooks
  by id (overlay keys win); ``disable: true`` removes a hook or a whole repo
"""

from __future__ import annotations

import copy
from typing import Any

CONFIG_FILES = {
    "pre-commit": ".pre-commit-config.yaml",
    "ruff": "ruff-base.toml",
    "clang-format": ".clang-format",
    "clang-tidy": ".clang-tidy",
    "clangd": ".clangd",
}


def deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = copy.deepcopy(base)
        for key, value in overlay.items():
            if value is None:
                result.pop(key, None)
            elif key in result:
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    return copy.deepcopy(overlay)


def split_checks(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    return [item.strip() for item in items if item and item.strip()]


def combine_checks(
    base: str | list[str] | None, overlay: str | list[str] | None
) -> str:
    result = split_checks(base)
    for item in split_checks(overlay):
        if item.startswith("-") and item[1:] in result:
            result.remove(item[1:])
        elif not item.startswith("-") and f"-{item}" in result:
            result.remove(f"-{item}")
        if item not in result:
            result.append(item)
    return ",".join(result)


def _options(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {item["key"]: item["value"] for item in value or [] if "key" in item}


def merge_clang_tidy(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    special = {"Checks", "WarningsAsErrors", "CheckOptions"}
    result = deep_merge(
        {k: v for k, v in base.items() if k not in special},
        {k: v for k, v in overlay.items() if k not in special},
    )
    for key in ("Checks", "WarningsAsErrors"):
        if key in base or key in overlay:
            result[key] = combine_checks(base.get(key), overlay.get(key))
    options = _options(base.get("CheckOptions"))
    for key, value in _options(overlay.get("CheckOptions")).items():
        if value is None:
            options.pop(key, None)
        else:
            options[key] = value
    if options:
        result["CheckOptions"] = [{"key": k, "value": v} for k, v in options.items()]
    order = [*base, *(k for k in overlay if k not in base)]  # keep the base's key order
    return {k: result[k] for k in order if k in result}


def merge_pre_commit(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deep_merge(
        {k: v for k, v in base.items() if k != "repos"},
        {k: v for k, v in overlay.items() if k != "repos"},
    )
    repos: list[dict[str, Any]] = [copy.deepcopy(r) for r in base.get("repos", [])]
    by_url = {r.get("repo"): r for r in repos}
    for extra in overlay.get("repos", []) or []:
        url = extra.get("repo")
        if extra.get("disable"):
            repos = [r for r in repos if r.get("repo") != url]
            by_url.pop(url, None)
            continue
        target = by_url.get(url)
        if target is None:
            new = {k: copy.deepcopy(v) for k, v in extra.items() if k != "hooks"}
            new["hooks"] = [
                copy.deepcopy(h) for h in extra.get("hooks", []) if not h.get("disable")
            ]
            repos.append(new)
            by_url[url] = new
            continue
        for key, value in extra.items():
            if key not in ("hooks", "repo"):
                target[key] = copy.deepcopy(value)
        hooks = target.setdefault("hooks", [])
        for hook in extra.get("hooks", []) or []:
            existing = next((h for h in hooks if h.get("id") == hook.get("id")), None)
            if hook.get("disable"):
                if existing is not None:
                    hooks.remove(existing)
            elif existing is not None:
                existing.update(copy.deepcopy(hook))
            else:
                hooks.append(copy.deepcopy(hook))
    result["repos"] = [
        r for r in repos if r.get("hooks") or r.get("repo") in ("local", "meta")
    ]
    return result


MERGERS = {
    "pre-commit": merge_pre_commit,
    "clang-tidy": merge_clang_tidy,
    "clang-format": deep_merge,
    "clangd": deep_merge,
}


def header(name: str, base_version: str, overlay: str | None) -> str:
    source = f"base {name} {base_version}" + (
        f" + overlay {overlay}" if overlay else ""
    )
    edit = f"edit {overlay}" if overlay else "add an overlay in main.ptk.yml (configs:)"
    return (
        f"# Generated by ptk from {source} - do not edit.\n"
        f"# To change it: {edit}, then run 'ptk setup configs sync'.\n"
    )
