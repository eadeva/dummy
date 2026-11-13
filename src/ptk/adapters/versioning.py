"""Read version sources and write atomic, content-stable generated files."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from ..domain.errors import PtkError
from ..domain.execution.model import CommandSpec
from ..domain.versioning import resolved, variables


def write_generated(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
    return True


def _with_distance(tag_value, distance, short, dirty):
    """1.0.9 + 57 commits -> 1.0.9+57.g<sha>; uncommitted changes add dirty."""
    suffix = [str(distance), "g" + short] if distance else []
    if dirty:
        suffix.append("dirty")
    if not suffix:
        return tag_value
    return tag_value + ("." if "+" in tag_value else "+") + ".".join(suffix)


def _build_label(tag_value, distance):
    """Build name from the nearest tag: '' (release), rc1, rc1-2 or dev57."""
    prerelease = tag_value.split("+", 1)[0].partition("-")[2]
    if not distance:
        return prerelease
    return f"{prerelease}-{distance}" if prerelease else f"dev{distance}"


class VersionIO:
    def __init__(self, runner, host):
        self.runner, self.host = runner, host

    def command(self, argv, root, timeout):
        lines = []
        result = self.runner.run(
            CommandSpec(
                argv=argv, cwd=str(root), env=dict(self.host.variables), timeout=timeout
            ),
            lines.append,
        )
        if result.exit_code:
            raise PtkError(
                f"version discovery command failed ({result.exit_code}): {' '.join(argv)}"
            )
        return "\n".join(lines).strip()

    def discover(self, spec, root):
        try:
            return self._discover(spec, root)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            yaml.YAMLError,
            PtkError,
        ) as exc:
            if spec.fallback is not None:
                item = self.discover(spec.fallback, root)
                return {**item, "fallback_used": True}
            raise PtkError(f"{spec.source} version discovery failed: {exc}") from None

    def _discover(self, spec, root):
        git = None
        if spec.source == "literal":
            raw = spec.version
        elif spec.source == "env":
            raw = self.host.variables.get(spec.variable, "")
        elif spec.source == "command":
            raw = self.command(spec.command, root, spec.timeout)
        elif spec.source == "file":
            path = (root / spec.path).resolve()
            raw = path.read_text(encoding="utf-8").strip()
            if spec.format != "text":
                data = {
                    "json": json.loads,
                    "toml": tomllib.loads,
                    "yaml": yaml.safe_load,
                }[spec.format](raw)
                for part in (spec.key or "").split("."):
                    if not part:
                        raise PtkError("structured version files require a dotted key")
                    data = data[part]
                if not isinstance(data, str):
                    raise PtkError("manifest version must be a string")
                raw = data
        elif spec.source == "git":

            def gitcmd(*args):
                return self.command(["git", *args], root, spec.timeout)

            shallow = gitcmd("rev-parse", "--is-shallow-repository") == "true"
            if shallow and not spec.allow_shallow:
                raise PtkError(
                    "shallow Git checkout: fetch full history/tags or explicitly set allow_shallow"
                )
            raw, tag, distance, short = self._describe(gitcmd, spec, "HEAD")
            dirty = bool(gitcmd("status", "--porcelain", "--untracked-files=no"))
            if dirty and spec.dirty == "error":
                raise PtkError("Git working tree is dirty")
            git = {
                "tag": tag,
                "distance": distance,
                "commit": gitcmd("rev-parse", "HEAD"),
                "dirty": dirty,
                "shallow": shallow,
            }
            tag_value = (
                tag.removeprefix(spec.strip_prefix) if spec.strip_prefix else tag
            )
            value = _with_distance(
                tag_value, distance, short, dirty and spec.dirty == "suffix"
            )
            result = resolved(value, raw=raw, source="git", git=git)
            result["build_label"] = _build_label(tag_value, distance)
            result["base"] = self._base(gitcmd, spec, result)
            return result
        else:
            raise PtkError("inherit is only valid for components")
        if spec.regex:
            match = re.search(spec.regex, raw)
            if not match:
                raise PtkError("version regex did not match")
            value = match.groupdict().get("version") or (
                match.group(1) if match.groups() else match.group()
            )
        else:
            value = raw.strip()
        if spec.strip_prefix:
            value = value.removeprefix(spec.strip_prefix)
        return resolved(value, raw=raw, source=spec.source)

    @staticmethod
    def _describe(gitcmd, spec, ref):
        args = ["describe", "--tags", "--long", "--abbrev=12", "--match", spec.match]
        if spec.first_parent:
            args.append("--first-parent")
        raw = gitcmd(*args, ref)
        match = re.fullmatch(r"(.+)-(\d+)-g([0-9a-f]+)", raw)
        if not match:
            raise PtkError("unexpected git describe result")
        tag, distance, short = match.groups()
        return raw, tag, int(distance), short

    def _base(self, gitcmd, spec, current):
        """Version where a pull request branched off; the build itself for other events."""
        same = {**{k: v for k, v in current.items() if k != "base"}, "ahead": 0}
        if not self.host.variables.get("GITHUB_EVENT_NAME", "").startswith(
            "pull_request"
        ):
            return same
        try:
            head = gitcmd("rev-parse", "--verify", "HEAD^2")
        except PtkError:
            return same  # not GitHub's synthetic merge commit
        fork = gitcmd("merge-base", "HEAD^1", head)
        raw, tag, distance, short = self._describe(gitcmd, spec, fork)
        tag_value = tag.removeprefix(spec.strip_prefix) if spec.strip_prefix else tag
        base = resolved(
            _with_distance(tag_value, distance, short, False), raw=raw, source="git"
        )
        base.update(
            build_label=_build_label(tag_value, distance),
            ahead=int(gitcmd("rev-list", "--count", f"{fork}..{head}")),
            commit=fork,
        )
        return base

    def snapshot(self, path, snapshot):
        write_generated(Path(path), yaml.safe_dump(snapshot, sort_keys=False))


def generate(snapshot, format, *, project=None, components=None, provenance=False):
    """Render build-system files from the same immutable run snapshot."""
    projects = snapshot["projects"]
    if project is not None:
        if project not in projects:
            raise PtkError(f"version project {project!r} was not resolved")
        projects = {project: projects[project]}
    if components is not None:
        if project is None:
            raise PtkError("component selection requires a project")
        if not isinstance(components, list):
            raise PtkError("components must be a list")
        selected = projects[project]
        missing = set(components) - selected["components"].keys()
        if missing:
            raise PtkError(f"unknown version components: {sorted(missing)}")
        projects = {
            project: {
                **selected,
                "components": {n: selected["components"][n] for n in components},
            }
        }
    values = variables({"projects": projects}, provenance=provenance)
    if format in ("header", "c_header"):
        lines = ["/* Generated by ptk. */", "#pragma once"]
        for key, value in values.items():
            lines.append(f"#define {key} {json.dumps(value, ensure_ascii=True)}")
        return "version.h", "\n".join(lines) + "\n"
    if format == "json":
        return "version.json", json.dumps(values, indent=2) + "\n"
    if format == "python":
        return "version.py", "# Generated by ptk.\n" + "\n".join(
            f"{k} = {v!r}" for k, v in values.items()
        ) + "\n"
    if format == "cmake":
        lines = ["# Generated by ptk."]
        for key, value in values.items():
            eq, text = "", str(value)
            while f"]{eq}]" in text:
                eq += "="
            lines.append(f"set({key} [{eq}[{text}]{eq}])")
        return "version.cmake", "\n".join(lines) + "\n"
    if format == "msbuild":

        def msvalue(v):
            # Escape MSBuild expansion syntax before XML encoding.
            text = str(v)
            for char in "%$@;'?*()":
                text = text.replace(char, f"%{ord(char):02X}")
            return escape(text)

        return "version.props", "<Project>\n  <PropertyGroup>\n" + "".join(
            f"    <{k}>{msvalue(v)}</{k}>\n" for k, v in values.items()
        ) + "  </PropertyGroup>\n</Project>\n"
    raise PtkError(f"unknown version generator format {format!r}")


def version_generator(step, out, ctx):
    if not ctx.versions:
        raise PtkError("version.generate requires versioning configuration")
    options = step.with_
    filename, text = generate(
        ctx.versions,
        options.get("format", "c_header"),
        project=options.get("project"),
        components=options.get("components"),
        provenance=options.get("provenance", False),
    )
    target = (
        Path(options["output"]) if options.get("output") else ctx.build_dir / filename
    )
    if not target.is_absolute():
        target = ctx.root / target
    if ctx.cancel and ctx.cancel.is_set():
        return 1
    changed = write_generated(target, text)
    out(f"{'generated' if changed else 'unchanged'} {target}")
    return 0
