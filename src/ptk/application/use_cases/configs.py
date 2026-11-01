"""Explicit external config copies, pinned identities and local-edit protection."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ...domain.errors import PtkError
from ...domain.shared_configs import MERGERS
from ..ports import SharedConfigFiles

LOCK = ".ptk-configs.lock.json"


def digest(value):
    return hashlib.sha256(value).hexdigest() if value is not None else None


@dataclass
class ConfigFile:
    name: str
    path: Path
    new_text: bytes | None
    old_text: bytes | None
    mode: int = 0o644
    old_mode: int | None = None
    expected: str | None = None
    stale: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def status(self):
        if self.old_text is None:
            return "new"
        wanted = self.expected if self.expected is not None else digest(self.new_text)
        return (
            "up to date"
            if not self.stale
            and digest(self.old_text) == wanted
            and self.old_mode == self.mode
            else "out of date"
        )

    def diff(self, root):
        rel = self.path.relative_to(root).as_posix()
        try:
            old = (self.old_text or b"").decode("utf-8")
            new = (self.new_text or b"").decode("utf-8")
        except UnicodeDecodeError:
            return f"Binary configuration changed: {rel}\n"
        text = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile="a/" + rel,
                tofile="b/" + rel,
            )
        )
        if self.old_mode != self.mode:
            text += f"Mode {rel}: {self.old_mode!s} -> {self.mode:o}\n"
        return text


class SharedConfigs:
    def __init__(self, files: SharedConfigFiles):
        self._files = files

    def _lock(self, root):
        content, mode = self._files.read(root, LOCK)
        if content is None:
            return {}, content, mode
        try:
            data = json.loads(content)
            if data.get("schema_version") != 1 or not isinstance(
                data.get("files"), dict
            ):
                raise ValueError("invalid fields")
            for record in data["files"].values():
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("sha256"), str)
                    or record.get("mode") not in (0o444, 0o555)
                ):
                    raise ValueError("invalid file record")
            return data, content, mode
        except (ValueError, TypeError, AttributeError) as exc:
            raise PtkError(f"invalid {LOCK}: {exc}") from None

    @staticmethod
    def _selection(project, names):
        groups = {
            name: spec for name, spec in project.config.configs.items() if spec.enabled
        }
        for name in names or []:
            if name not in groups:
                raise PtkError(f"configuration group {name!r} is not enabled")
        return {
            name: spec for name, spec in groups.items() if not names or name in names
        }

    def _overlay(self, project, item):
        if not item.overlay:
            return None
        content, _ = self._files.read(project.root, item.overlay)
        if content is None:
            raise PtkError(f"overlay file not found: {item.overlay}")
        return content

    @staticmethod
    def _merge(name, base, overlay):
        if overlay is None:
            return base
        try:
            data, override = yaml.safe_load(base), yaml.safe_load(overlay)
            if not isinstance(data, dict) or not isinstance(override, dict):
                raise TypeError("base and overlay must be YAML mappings")
            return yaml.safe_dump(
                MERGERS[name](data, override), sort_keys=False, allow_unicode=True
            ).encode()
        except (yaml.YAMLError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise PtkError(f"cannot merge {name} configuration: {exc}") from None

    @staticmethod
    def _entries(groups):
        for name, spec in groups.items():
            for item in spec.files:
                yield name, item, item.destination, None
                if item.output:
                    yield name, item, item.output, item.overlay

    def check(self, project, names=None):
        """Read-only offline validation; no cache creation, fetch or tag lookup."""
        groups = self._selection(project, names)
        previous, raw, mode = self._lock(project.root)
        source = project.config.configs.source
        identity = source.model_dump() if source else None
        same_source = previous.get("source") == identity
        result = []
        desired = set()
        for name, item, destination, overlay_path in self._entries(groups):
            desired.add(destination)
            old, old_mode = self._files.read(project.root, destination)
            record = previous.get("files", {}).get(destination, {})
            overlay = self._overlay(project, item) if overlay_path else None
            result.append(
                ConfigFile(
                    name,
                    project.root / destination,
                    None,
                    old,
                    mode=record.get("mode", 0o444) if os.name != "nt" else 0o444,
                    old_mode=old_mode & ~0o222 if old_mode is not None else None,
                    expected=record.get("sha256"),
                    stale=not same_source
                    or record.get("source") != item.source
                    or record.get("group") != name
                    or record.get("overlay") != overlay_path
                    or record.get("overlay_sha256") != digest(overlay),
                )
            )
        recorded = {
            path
            for path, record in previous.get("files", {}).items()
            if not names or record.get("group") in names
        }
        if desired != recorded or result and not same_source:
            result.append(
                ConfigFile(
                    "lock", project.root / LOCK, raw, raw, old_mode=mode, stale=True
                )
            )
        return result

    def plan(self, project, names=None):
        with self._files.transaction(project.root):
            return self._plan(project, names)

    def _plan(self, project, names=None):
        groups = self._selection(project, names)
        previous, raw, old_mode = self._lock(project.root)
        source = project.config.configs.source
        identity = source.model_dump() if source else None
        if names and previous and previous.get("source") != identity:
            raise PtkError(
                "source/revision changed; synchronize all configuration groups together"
            )
        paths = [item.source for spec in groups.values() for item in spec.files]
        pinned = previous.get("commit") if previous.get("source") == identity else None
        if paths:
            commit, blobs = self._files.snapshot(project.root, source, pinned, paths)
        else:
            commit, blobs = pinned, {}
        records = {
            path: record
            for path, record in previous.get("files", {}).items()
            if names and record.get("group") not in names
        }
        changes = []
        for name, item, destination, overlay_path in self._entries(groups):
            content, mode = blobs[item.source]
            overlay = self._overlay(project, item) if overlay_path else None
            content = self._merge(name, content, overlay)
            if overlay is not None:
                provenance = json.dumps(
                    {
                        "repository": source.repository,
                        "revision": source.revision,
                        "commit": commit,
                        "source": item.source,
                        "overlay": overlay_path,
                    }
                )
                content = (
                    "# Generated by PTK; do not edit. Edit the project overlay instead.\n# "
                    + provenance
                    + "\n"
                ).encode() + content
            mode = (mode if os.name != "nt" else 0o644) & ~0o222
            old, current_mode = self._files.read(project.root, destination)
            owned = previous.get("files", {}).get(destination)
            wanted = (digest(content), mode)
            # Equal bytes may be adopted and made read-only on initial sync.
            if (
                old is not None
                and digest(old) != wanted[0]
                and (not owned or digest(old) != owned["sha256"])
            ):
                raise PtkError(
                    f"preserving locally modified or unowned configuration: {destination}; reconcile it before synchronization"
                )
            records[destination] = {
                "group": name,
                "source": item.source,
                "sha256": wanted[0],
                "mode": mode,
                "overlay": overlay_path,
                "overlay_sha256": digest(overlay),
                "kind": "generated" if overlay_path else "external-base",
            }
            changes.append(
                ConfigFile(
                    name,
                    project.root / destination,
                    content,
                    old,
                    mode=mode,
                    old_mode=current_mode,
                    notes=[
                        f"{records[destination]['kind']}: {source.repository}@{commit}:{item.source}"
                        + (
                            f" + overlay {overlay_path}"
                            if overlay_path
                            else " (read-only; do not edit)"
                        )
                    ],
                )
            )
        if not paths and not previous:
            return []
        document = {
            "schema_version": 1,
            "source": identity,
            "commit": commit,
            "files": records,
        }
        content = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
        changes.append(
            ConfigFile("lock", project.root / LOCK, content, raw, old_mode=old_mode)
        )
        return changes

    def sync(self, project, names=None):
        with self._files.transaction(project.root):
            planned = self._plan(project, names)
            # All sources, destinations and conflicts are checked before any project write.
            for item in planned:
                if item.status != "up to date":
                    self._files.write(
                        project.root,
                        item.path.relative_to(project.root).as_posix(),
                        item.new_text,
                        item.mode,
                    )
            return planned
