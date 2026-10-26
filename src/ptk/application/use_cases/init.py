"""Create a runnable project with a minimal entry file and organized config."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...domain.errors import PtkError
from ..ports import ProjectScaffold, WorkspaceMember

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


def repository_alias(name: str) -> str:
    alias = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    if not alias or not alias[0].isalpha():
        alias = "repo-" + (alias or "project")
    return alias


class InitProject:
    def __init__(self, scaffold: ProjectScaffold):
        self._scaffold = scaffold

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
                    "include": "project.ptk.yml",
                }
            ),
            ".gitignore": IGNORE,
        }
        configs = {
            "workflow.ptk.yml": "# Local orchestration; run `ptk workflow run verify`. Not executed on CX.\n"
            "# Nest steps under parallel: true for independent action calls.\n"
            "# open_report: always (default), on-errors, or null to disable opening.\n"
            + dump(
                {
                    "workflows": {
                        "verify": {
                            "help": "Run the starter actions locally",
                            "open_report": "always",
                            "steps": [
                                {"hello": {"action": "hello"}},
                                {"build": {"action": "build"}},
                            ],
                        }
                    }
                }
            ),
            "project.ptk.yml": "# Composition root: includes are relative to this file.\n"
            "# Add actions as separate files under actions/; the glob loads them.\n"
            + dump(
                {
                    "schema_version": 1,
                    "include": [
                        "tools/tools.ptk.yml",
                        "versioning/versioning.ptk.yml",
                        "environment/environment.ptk.yml",
                        "credentials/credentials.ptk.yml",
                        "configs/configs.ptk.yml",
                        "actions/*.ptk.yml",
                    ],
                    "project": {"name": name, "default_action": "hello"},
                    "variants": "variants/variants.ptk.yml",
                }
            )
            + "# Optional project-wide parameter defaults (only for declared parameters):\n"
            "# param_defaults: {jobs: 4}\n"
            "# logging: {level: info, keep_history: 10}\n"
            "# reporting: {formats: [json, html]}\n",
            "actions/hello.ptk.yml": '# First action: try `ptk hello --message "Hello" -V debug`.\n'
            + dump(
                {
                    "actions": {
                        "hello": {
                            "help": "Print a message and the selected project version",
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
                            ],
                        }
                    }
                }
            )
            + "# Action options (place alongside help/params/steps):\n"
            "#     audience: maintainer  # Restrict this action to listed maintainers.\n"
            "#     open_report: on_errors  # always | on_errors; disabled on CX.\n"
            "#     env: {GREETING_STYLE: friendly}  # Applies only to this action.\n",
            "actions/build.ptk.yml": "# Second action: a portable build starter; no compiler installation needed.\n"
            "# Run `ptk build -V release`; replace/extend these steps for your build.\n"
            + dump(
                {
                    "actions": {
                        "build": {
                            "help": "Generate version files for C/C++ and CMake",
                            "steps": [
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
            )
            + "# After declaring cmake in tools/tools.ptk.yml, add beside steps:\n"
            "#     requires_tools: {cmake: true}\n"
            "# Example additional step (under steps, after creating CMakeLists.txt):\n"
            "#       - configure:\n"
            '#           run: [cmake, -S, ., -B, "${run.build_dir}"]\n'
            "#           timeout: 120\n",
            "variants/variants.ptk.yml": "# Variant model: includes here are relative to variants/.\n"
            "# Add a separate file per variant and include it below.\n"
            + dump(
                {
                    "include": ["debug.ptk.yml", "release.ptk.yml"],
                    "default": "debug",
                    "components": {
                        "core": {
                            "description": "Example project component",
                            "features": {
                                "DEBUG": {
                                    "type": "bool",
                                    "default": True,
                                    "help": "Enable debug behavior",
                                }
                            },
                        }
                    },
                }
            ),
            "variants/debug.ptk.yml": "# Development variant; feature values are exported as VH_* variables.\n"
            + dump(
                {
                    "variants": {
                        "debug": {
                            "description": "Development build",
                            "features": {"DEBUG": True},
                        }
                    }
                }
            ),
            "variants/release.ptk.yml": "# Release variant; select with -V release.\n"
            + dump(
                {
                    "variants": {
                        "release": {
                            "description": "Release build",
                            "features": {"DEBUG": False},
                        }
                    }
                }
            ),
            "tools/tools.ptk.yml": """# Tool definitions and global requirements. Nothing is installed by this starter.
# Uncomment the tool, then enable it in an action's requires_tools.
tools: {}
requires_tools: {}
# Replace tools: {} with, for example:
# tools:
#   cmake:
#     version: ">=3.30,<4"           # Accepted version range.
#     check: cmake --version         # Command used to verify the tool.
#     uv_tool: "cmake==3.30.2"       # Isolated, pinned Python tool installation.
# Or use a managed archive source for a tool:
#     download:
#       url: https://example.com/tool.zip  # Replace with the real download URL.
#       sha256: REPLACE_WITH_SHA256       # Verify the downloaded archive.
#       bin: bin                         # Executable directory inside the archive.
# requires_tools: {cmake: true}     # Require globally instead of per action.
""",
            "versioning/versioning.ptk.yml": "# Literal version works before you create any Git tags.\n"
            + dump(
                {
                    "versioning": {
                        "project": {"source": "literal", "version": "0.1.0"},
                        "components": {"core": {"source": "inherit"}},
                    }
                }
            )
            + "# To discover a tagged version, replace project above with:\n"
            "#   project:\n"
            "#     source: git\n"
            '#     match: "v*"          # Select reachable tags matching this pattern.\n'
            "#     strip_prefix: v      # v1.2.3 becomes 1.2.3.\n"
            "#     dirty: suffix        # suffix, ignore or error.\n"
            "# A separately versioned component can use source: file, path: VERSION.\n"
            "# Paths in version sources are relative to the repository root.\n",
            "environment/environment.ptk.yml": "# Child commands get only OS essentials and explicitly kept variables.\n"
            + dump(
                {"environment": {"isolate": True, "inherit_path": False, "keep": []}}
            )
            + "# Under environment, customize only what commands need:\n"
            "#   keep: [HTTP_PROXY, HTTPS_PROXY]  # Copy named variables from the caller.\n"
            "#   set: {BUILD_MODE: reproducible} # Set values for all actions.\n"
            "#   unset: [UNWANTED_VARIABLE]      # Remove inherited variables.\n"
            "#   path_prepend: [/opt/sdk/bin]    # Explicit extra executable paths.\n"
            "#   path_append: []\n",
            "credentials/credentials.ptk.yml": """# Credential declarations only; never put actual secret values here.
credentials: {}
# Replace credentials: {} with an entry such as:
# credentials:
#   registry:
#     description: Package registry access
#     fields: [token]
#     providers: [env, vault, prompt]  # Tried in this order.
#     env: {token: REGISTRY_TOKEN}    # Read this variable from the caller.
# Then inject it only in a step that needs it:
#     secrets: {REGISTRY_TOKEN: registry.token}
# Provision using `ptk setup creds`; do not commit secret values.
""",
            "configs/configs.ptk.yml": """# Shared formatter/linter configuration. Enable entries you intend to use.
configs: {}
# Replace configs: {} with, for example:
# configs:
#   ruff: {enabled: true}           # Python lint/format configuration.
#   clang-format: {enabled: true}   # C/C++ formatting configuration.
# Run `ptk setup configs sync` to generate the enabled configuration files.
""",
            "cx.ptk.yml": """# Conventional entry point: loaded automatically for GitHub Actions/workflows.
# This file stays at the configuration root so PTK can discover it.
environment:
  set:
    PTK_CI: "true"
# Optional action override; place at the top level:
# actions:
#   build:
#     env: {BUILD_MODE: ci}
""",
            "maintainers.ptk.yml": """# Conventional entry point for maintainer identities; stays at config root.
maintainers: []
# Replace maintainers: [] with real identities before restricting actions:
# maintainers:
#   - name: Project Maintainer
#     email: maintainer@example.com  # Matches this repository's Git identity.
#     user: maintainer              # Optional operating-system username.
# Set audience: maintainer on an action to restrict it.
""",
        }
        files.update(
            {(folder / n).as_posix(): content for n, content in configs.items()}
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
                    "rerun setup init to initialize the remaining repositories."
                ) from None
            results[directory] = InitResult(plan.files, kept, False)
        return results
