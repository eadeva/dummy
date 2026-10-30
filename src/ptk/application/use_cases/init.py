"""Create a runnable project with a minimal entry file and organized config."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...domain.errors import PtkError
from ..ports import HostEnvironment, ProjectScaffold, WorkspaceMember

IGNORE = """# PTK generated workspace
.ptk/
_builds/
_bin/
_logs/
_reports/
.gen.version.ptk.yml
"""


@dataclass(frozen=True)
class InitResult:
    files: dict[str, str]
    kept_gitignore: bool
    dry_run: bool


def repository_alias(name: str) -> str:
    alias = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    if not alias or not alias[0].isalpha():
        alias = "repo-" + (alias or "project")
    return alias


class InitProject:
    def __init__(self, scaffold: ProjectScaffold, host: HostEnvironment | None = None):
        self._scaffold = scaffold
        self._host = host

    def execute(
        self,
        target: Path,
        name: str | None = None,
        *,
        config_path: str,
        dry_run=False,
        alias: str | None = None,
    ):
        name = target.resolve().name if name is None else name.strip()
        if not name or any(ord(char) < 32 for char in name):
            raise PtkError(
                "project name must be non-empty and contain no control characters"
            )
        folder = Path(config_path)
        if (
            not str(config_path).strip()
            or folder.is_absolute()
            or ".." in folder.parts
            or any(ord(c) < 32 for c in str(config_path))
            or not (target / folder).resolve().is_relative_to(target.resolve())
        ):
            raise PtkError("configuration directory must stay within the repository")
        if any(
            part in {".git", ".repo", ".ptk", "_builds", "_logs", "_reports", "_bin"}
            for part in folder.parts
        ):
            raise PtkError(
                "configuration directory cannot be a generated or Git metadata directory"
            )
        alias = repository_alias(name) if alias is None else alias

        def dump(value):
            return yaml.safe_dump(value, sort_keys=False, allow_unicode=True)

        files = {
            ".main.ptk.yml": dump(
                {
                    "repository": {"alias": alias, "config_path": folder.as_posix()},
                }
            ),
            ".gitignore": IGNORE,
        }
        configs = {
            "project.ptk.yml": {
                "name": name,
                "default_job": "hello",
                "components": {"core": {"path": "components/core"}},
                "environment": {"isolate": True, "inherit_path": False, "keep": []},
            },
            "folder_structure.ptk.yml": {
                "builds": "_builds",
                "bin": "_bin",
                "logs": "_logs",
                "reports": "_reports",
            },
            "workflows/verify.ptk.yml": {
                "help": "Run the starter jobs locally",
                "open_report": "always",
                "jobs": {
                    "hello": {"job": "hello"},
                    "build": {"job": "build", "needs": "hello"},
                },
            },
            "jobs/hello.ptk.yml": {
                "help": "Print a message and the selected project version",
                "params": {
                    "message": {
                        "default": "Hello from ptk",
                        "help": "Message to display",
                    }
                },
                "steps": {
                    "greet": {"uses": "echo", "with": {"message": "${params.message}"}},
                    "version": {
                        "uses": "echo",
                        "with": {
                            "message": "Version ${version.projects."
                            + alias
                            + ".value} (${vh.variant})"
                        },
                        "needs": ["greet"],
                    },
                },
            },
            "jobs/build.ptk.yml": {
                "help": "Generate version files for C/C++ and CMake",
                "steps": {
                    "header": {
                        "uses": "version.generate",
                        "with": {
                            "format": "c_header",
                            "output": "${run.bin_dir}/generated/version.h",
                        },
                    },
                    "cmake": {
                        "uses": "version.generate",
                        "with": {
                            "format": "cmake",
                            "output": "${run.bin_dir}/generated/version.cmake",
                        },
                        "needs": ["header"],
                    },
                },
            },
            "project.variants.ptk.yml": {"default": "debug"},
            "variants/debug.ptk.yml": {
                "description": "Development build",
                "features": {"core.DEBUG": True},
            },
            "variants/release.ptk.yml": {
                "description": "Release build",
                "features": {"core.DEBUG": False},
            },
            "tools.ptk.yml": {},
            "versioning.ptk.yml": {
                "project": {"source": "literal", "version": "0.1.0"},
                "components": {"core": {"source": "inherit"}},
            },
            "credentials.ptk.yml": {},
            "configs.ptk.yml": {},
            "maintainers.ptk.yml": {
                "maintainers": [user]
                if self._host and (user := self._host.user_id())
                else []
            },
        }
        notes = {
            "project.ptk.yml": "Project settings and component directories (relative to the repository root).",
            "folder_structure.ptk.yml": "Output folders; these are also PTK's defaults when this file is absent.",
            "workflows/verify.ptk.yml": "Local orchestration: ptk workflow run verify. The filename supplies the workflow name.",
            "jobs/hello.ptk.yml": 'Try: ptk hello --message "Hello" -V debug. The filename supplies the job name.',
            "jobs/build.ptk.yml": "Portable starter: ptk build -V release. Replace these steps with your build.",
            "project.variants.ptk.yml": "Project default variant and optional constraints/env settings.",
            "variants/debug.ptk.yml": "Feature values are exported as VARIANT_* variables.",
            "variants/release.ptk.yml": "Release feature selection; select with -V release.",
            "tools.ptk.yml": "Tool declarations. Require tools in project.ptk.yml or an individual job.",
            "versioning.ptk.yml": "Literal version works before Git tags exist. Source paths are repository-relative.",
            "credentials.ptk.yml": "Credential declarations only. Use env/vault/prompt providers for actual secrets.",
            "configs.ptk.yml": "Shared formatter/linter settings, for example ruff: {enabled: true}.",
            "maintainers.ptk.yml": "Maintainer login IDs: local OS usernames or triggering GitHub actors.",
        }
        files.update(
            {
                (folder / filename).as_posix(): "# "
                + notes[filename]
                + "\n"
                + dump(value)
                for filename, value in configs.items()
            }
        )
        files["components/core/component.variants.ptk.yml"] = (
            "# Keep component features, dependencies and constraints beside its CMakeLists.txt or Bazel module.\n"
            + dump(
                {
                    "description": "Example project component",
                    "features": {
                        "DEBUG": {
                            "type": "bool",
                            "default": True,
                            "help": "Enable debug behavior",
                        }
                    },
                }
            )
        )
        kept = self._scaffold.create(target, files, dry_run=dry_run)
        return InitResult(files, kept, dry_run)

    def execute_workspace(
        self,
        root: Path,
        members: list[WorkspaceMember],
        *,
        config_path: str,
        dry_run=False,
        reserved: Collection[str] = (),
    ) -> dict[Path, InitResult]:
        """Preflight all new repositories and keep existing configurations intact."""
        used = set(reserved) | {member.alias for member in members if member.alias}
        plans = {}
        for member in members:
            if member.skip_reason is not None:
                continue
            alias = repository_alias(member.root.name)
            if alias in used:
                alias = repository_alias(member.root.relative_to(root).as_posix())
            base, suffix = alias, 2
            while alias in used:
                alias = f"{base}-{suffix}"
                suffix += 1
            used.add(alias)
            plans[member.root] = self.execute(
                member.root, config_path=config_path, dry_run=True, alias=alias
            )
        if dry_run:
            return plans
        results = {}
        for directory, plan in plans.items():
            try:
                kept = self._scaffold.create(directory, plan.files, dry_run=False)
            except PtkError as exc:
                raise PtkError(
                    f"{exc}\nInitialized {len(results)} repositories before this error; "
                    "rerun init to initialize the remaining repositories."
                ) from None
            results[directory] = InitResult(plan.files, kept, False)
        return results
