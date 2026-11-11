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

    @staticmethod
    def lock_path(project):
        return (
            (project.config_root / LOCK).relative_to(project.root.resolve()).as_posix()
        )

    def _lock(self, project):
        path = self.lock_path(project)
        content, mode = self._files.read(project.root, path)
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
                    or not isinstance(record.get("mode"), int)
                    or not 0 <= record["mode"] <= 0o777
                ):
                    raise ValueError("invalid file record")
            return data, content, mode
        except (ValueError, TypeError, AttributeError) as exc:
            raise PtkError(f"invalid {path}: {exc}") from None

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

    def _files_of(self, groups, sources):
        """(group, item, destination, overlay, source file); folders expand to their files."""
        for name, item, destination, overlay_path in self._entries(groups):
            if not item.source.endswith("/"):
                yield name, item, destination, overlay_path, item.source
                continue
            found = sorted(p for p in sources if p.startswith(item.source))
            for path in found:
                yield (
                    name,
                    item,
                    item.destination + path[len(item.source) :],
                    None,
                    path,
                )

    @staticmethod
    def _recorded_sources(previous, groups):
        return {
            record.get("source")
            for record in previous.get("files", {}).values()
            if record.get("group") in groups and record.get("mapping")
        }

    def check(self, project, names=None):
        """Read-only offline validation; no cache creation, fetch or tag lookup."""
        groups = self._selection(project, names)
        previous, raw, mode = self._lock(project)
        source = project.config.configs.source
        identity = source.model_dump() if source else None
        same_source = previous.get("source") == identity
        result = []
        desired = set()
        empty_folder = any(
            item.source.endswith("/")
            and not any(
                r.get("mapping") == item.source and r.get("group") == name
                for r in previous.get("files", {}).values()
            )
            for name, spec in groups.items()
            for item in spec.files
        )
        for name, item, destination, overlay_path, source_path in self._files_of(
            groups, self._recorded_sources(previous, groups)
        ):
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
                    mode=(record.get("mode", 0o644) & 0o111) if os.name != "nt" else 0,
                    old_mode=old_mode & 0o111 if old_mode is not None else None,
                    expected=record.get("sha256"),
                    stale=not same_source
                    or record.get("source") != source_path
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
        if desired != recorded or empty_folder or result and not same_source:
            result.append(
                ConfigFile(
                    "lock",
                    project.root / self.lock_path(project),
                    raw,
                    raw,
                    old_mode=mode,
                    stale=True,
                )
            )
        return result

    def plan(self, project, names=None):
        with self._files.transaction(project.root):
            return self._plan(project, names)

    def _plan(self, project, names=None, confirm=None):
        groups = self._selection(project, names)
        previous, raw, old_mode = self._lock(project)
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
        conflicts = []
        for name, item, destination, overlay_path, source_path in self._files_of(
            groups, blobs
        ):
            content, mode = blobs[source_path]
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
            mode = mode if os.name != "nt" else 0o644
            old, current_mode = self._files.read(project.root, destination)
            owned = previous.get("files", {}).get(destination)
            wanted = (digest(content), mode)
            # Equal bytes may be adopted on initial sync.
            if (
                old is not None
                and digest(old) != wanted[0]
                and (not owned or digest(old) != owned["sha256"])
            ):
                conflicts.append(destination)
            records[destination] = {
                "group": name,
                "source": source_path,
                "sha256": wanted[0],
                "mode": mode,
                "overlay": overlay_path,
                "overlay_sha256": digest(overlay),
                "kind": "generated" if overlay_path else "external-base",
            }
            if source_path != item.source:
                records[destination]["mapping"] = item.source
            changes.append(
                ConfigFile(
                    name,
                    project.root / destination,
                    content,
                    old,
                    mode=mode,
                    old_mode=current_mode,
                    notes=[
                        f"{records[destination]['kind']}: {source.repository}@{commit}:{source_path}"
                        + (
                            f" + overlay {overlay_path}"
                            if overlay_path
                            else " (external base; do not edit)"
                        )
                    ],
                )
            )
        if conflicts and not (confirm and confirm(conflicts)):
            raise PtkError(
                "preserving locally modified or unowned configuration: "
                + ", ".join(conflicts)
                + "; reconcile it before synchronization or use --force"
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
            ConfigFile(
                "lock",
                project.root / self.lock_path(project),
                content,
                raw,
                old_mode=old_mode,
            )
        )
        return changes

    def sync(self, project, names=None, confirm=None):
        """``confirm(paths)`` may accept overwriting locally changed or unowned files."""
        with self._files.transaction(project.root):
            planned = self._plan(project, names, confirm)
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

    def deviations(self, project):
        """Describe local effective YAML differences using hash-verified bases only."""
        previous, _, _ = self._lock(project)
        source = project.config.configs.source
        identity = source.model_dump() if source else None
        groups = self._selection(project, None)
        if any(spec.files for spec in groups.values()) and (
            not previous or previous.get("source") != identity
        ):
            raise PtkError(
                "synchronize the configured source before reporting deviations"
            )
        report = {
            "report_type": "ptk-config-deviations",
            "schema_version": 1,
            "source": identity,
            "commit": previous.get("commit"),
            "deviations": [],
            "modified_base_files": [],
            "unavailable": [],
        }
        records = previous.get("files", {})
        for name, spec in groups.items():
            for item in spec.files:
                if item.source.endswith("/"):
                    for path, record in records.items():
                        if record.get("mapping") != item.source:
                            continue
                        base, _ = self._files.read(project.root, path)
                        if base is None:
                            report["unavailable"].append(
                                {"path": path, "reason": "base missing"}
                            )
                        elif digest(base) != record.get("sha256"):
                            report["modified_base_files"].append(path)
                    continue
                base, _ = self._files.read(project.root, item.destination)
                record = records.get(item.destination, {})
                reason = None
                if record.get("source") != item.source or record.get("group") != name:
                    reason = "mapping not synchronized"
                elif base is None:
                    reason = "base missing"
                elif digest(base) != record.get("sha256"):
                    report["modified_base_files"].append(item.destination)
                    reason = "base modified; comparison omitted"
                if reason:
                    report["unavailable"].append(
                        {"path": item.destination, "reason": reason}
                    )
                    continue
                if not item.output:
                    continue
                effective, _ = self._files.read(project.root, item.output)
                if effective is None:
                    report["unavailable"].append(
                        {"path": item.output, "reason": "output missing"}
                    )
                    continue
                try:
                    before = yaml.safe_dump(
                        yaml.safe_load(base), sort_keys=True, allow_unicode=True
                    )
                    after = yaml.safe_dump(
                        yaml.safe_load(effective), sort_keys=True, allow_unicode=True
                    )
                except (yaml.YAMLError, UnicodeError, TypeError, ValueError) as exc:
                    report["unavailable"].append(
                        {"path": item.output, "reason": f"invalid YAML: {exc}"}
                    )
                    continue
                diff = "".join(
                    difflib.unified_diff(
                        before.splitlines(keepends=True),
                        after.splitlines(keepends=True),
                        fromfile=item.destination,
                        tofile=item.output,
                    )
                )
                if diff:
                    output_record = records.get(item.output, {})
                    report["deviations"].append(
                        {
                            "group": name,
                            "base": item.destination,
                            "overlay": item.overlay,
                            "output": item.output,
                            "output_matches_sync": digest(effective)
                            == output_record.get("sha256"),
                            "diff": diff,
                        }
                    )
        return report

    def write_deviations(self, project, output):
        from ...domain.shared_configs import destination_path

        try:
            destination_path(output)
        except ValueError as exc:
            raise PtkError(str(exc)) from None
        reserved = {self.lock_path(project).casefold()}
        for spec in (spec for name, spec in project.config.configs.items()):
            for item in spec.files:
                reserved.update(
                    p.casefold()
                    for p in (item.destination, item.overlay, item.output)
                    if p
                )
        if output.casefold() in reserved:
            raise PtkError("report output cannot replace a configuration file")
        with self._files.transaction(project.root):
            existing, _ = self._files.read(project.root, output)
            if existing is not None:
                try:
                    owned = (
                        json.loads(existing).get("report_type")
                        == "ptk-config-deviations"
                    )
                except (ValueError, AttributeError):
                    owned = False
                if not owned:
                    raise PtkError(
                        "report output exists and is not a PTk configuration deviations report"
                    )
            report = self.deviations(project)
            self._files.write(
                project.root,
                output,
                (json.dumps(report, indent=2) + "\n").encode(),
                0o644,
            )
        return report
