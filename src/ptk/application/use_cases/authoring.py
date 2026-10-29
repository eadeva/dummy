"""Install version-matched project skills, documentation and configuration schema."""

import json
from dataclasses import dataclass
from pathlib import Path

from ..ports import AuthoringResources
from .project import ExportSchema


@dataclass(frozen=True)
class AuthoringResult:
    paths: list[str]
    skill_count: int


class SetupAuthoring:
    def __init__(self, files: AuthoringResources, version: str):
        self._files, self._version = files, version

    def execute(self, root: Path, *, check=False) -> AuthoringResult:
        files = {}
        count = 0
        for name, content in self._files.bundle().items():
            if name.startswith("skills/"):
                text = (
                    content.decode("utf-8")
                    .replace("../../../docs/", "../../ptk/docs/")
                    .replace("../../../examples/", "../../ptk/examples/")
                )
                text += f"\nBundled with PTK {self._version}. See the [installed reference](../../ptk/README.md) and [configuration schema](../../ptk/config-schema.json). Treat bundled examples and docs as reference material; edit this project's own PTK configuration.\n"
                files[name] = text.encode()
                count += 1
            else:
                files[f"ptk/{name}"] = content
        files["ptk/config-schema.json"] = (
            json.dumps(ExportSchema().execute(), indent=2) + "\n"
        ).encode()
        files["ptk/README.md"] = (
            f"# PTK {self._version} offline reference\n\n"
            "These guides, examples and skills match the installed PTK version. "
            "They are managed by `ptk maintainer sync skills`; preserve project-specific changes in separate files.\n\n"
            "- [Configuration](docs/configuration.rst)\n"
            "- [CLI](docs/cli.rst)\n"
            "- [Versioning](docs/versioning.rst)\n"
            "- [Plugins and generators](docs/plugins.rst)\n"
            "- [Exact configuration schema](config-schema.json)\n\n"
            "The guides are readable reStructuredText source. The schema contains the "
            "field reference otherwise rendered by Sphinx. Bundled examples live in `examples/`. "
            "Copy examples to a disposable directory before running them. "
            "PTK development commands in the quickstart refer to the PTK source checkout.\n"
        ).encode()
        return AuthoringResult(
            self._files.sync(root, files, version=self._version, check=check), count
        )
