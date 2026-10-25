"""Create a runnable project with a minimal entry file and organized config."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...domain.errors import PtkError
from ..ports import ProjectScaffold

IGNORE = """# ptk generated workspace and local overrides
.ptk/
_builds/
_bin/
_logs/
_reports/
local.ptk.yml
.gen.version.ptk.yml
"""


@dataclass(frozen=True)
class InitResult:
    files: dict[str, str]
    kept_gitignore: bool
    dry_run: bool


class InitProject:
    def __init__(self, scaffold: ProjectScaffold):
        self._scaffold = scaffold

    def execute(
        self, target: Path, name: str | None = None, *, config_path="ptk", dry_run=False
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
        alias = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
        if not alias or not alias[0].isalpha():
            alias = "repo-" + (alias or "project")

        def dump(value):
            return yaml.safe_dump(value, sort_keys=False, allow_unicode=True)

        files = {
            ".main.ptk.yml": dump(
                {
                    "repository": {"alias": alias, "config_path": folder.as_posix()},
                    "include": "project.ptk.yml",
                }
            ),
            ".gitignore": IGNORE,
        }
        configs = {
            "project.ptk.yml": dump(
                {
                    "schema_version": 1,
                    "include": [
                        "actions.ptk.yml",
                        "environment.ptk.yml",
                        "credentials.ptk.yml",
                        "configs.ptk.yml",
                    ],
                    "project": {"name": name, "default_action": "hello"},
                    "variants": "variants.ptk.yml",
                }
            ),
            "actions.ptk.yml": dump(
                {
                    "actions": {
                        "hello": {
                            "help": "Try parameters, variants and version generation",
                            "params": {
                                "message": {
                                    "default": "Hello from ptk",
                                    "help": "Message to display",
                                }
                            },
                            "steps": [
                                {
                                    "greet": {
                                        "uses": "echo",
                                        "with": {"message": "${params.message}"},
                                    }
                                },
                                {
                                    "version": {
                                        "uses": "echo",
                                        "with": {
                                            "message": "Version ${version.projects."
                                            + alias
                                            + ".value} (${vh.variant})"
                                        },
                                    }
                                },
                                {
                                    "header": {
                                        "uses": "version.generate",
                                        "with": {
                                            "format": "c_header",
                                            "output": "${run.bin_dir}/generated/version.h",
                                        },
                                    }
                                },
                                {
                                    "cmake": {
                                        "uses": "version.generate",
                                        "with": {
                                            "format": "cmake",
                                            "output": "${run.bin_dir}/generated/version.cmake",
                                        },
                                    }
                                },
                            ],
                        }
                    }
                }
            ),
            "variants.ptk.yml": dump(
                {
                    "default": "debug",
                    "components": {},
                    "variants": {"debug": {}, "release": {}},
                }
            ),
            "tools.ptk.yml": "# Declare managed download or uv_tool sources here; enable tools with requires_tools.\ntools: {}\nrequires_tools: {}\n",
            "versioning.ptk.yml": "# Switch to source: git, match: 'v*', strip_prefix: v when tags are available.\n"
            + dump(
                {
                    "versioning": {
                        "project": {"source": "literal", "version": "0.1.0"},
                        "components": {"core": {}},
                    }
                }
            ),
            "environment.ptk.yml": dump(
                {"environment": {"isolate": True, "inherit_path": False, "keep": []}}
            ),
            "credentials.ptk.yml": "# Declare credential providers here; never commit secret values.\ncredentials: {}\n",
            "configs.ptk.yml": "# Enable shared formatter/linter configuration with ptk setup configs.\nconfigs: {}\n",
            "cx.ptk.yml": "# GitHub Actions/workflows overlay, loaded automatically in CI.\n{}\n",
            "maintainers.ptk.yml": "# Optional identities for maintainer-only actions.\nmaintainers: []\n",
        }
        files.update(
            {(folder / n).as_posix(): content for n, content in configs.items()}
        )
        kept = self._scaffold.create(target, files, dry_run=dry_run)
        return InitResult(files, kept, dry_run)
