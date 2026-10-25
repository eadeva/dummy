"""Include authoring assets in wheels, including wheels rebuilt from sdists."""

import importlib.util
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class AuthoringBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        spec = importlib.util.spec_from_file_location(
            "ptk_authoring_bundle", root / "src/ptk/authoring_bundle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for destination, source in module.source_files(root).items():
            build_data["force_include"][str(source)] = (
                f"ptk/resources/authoring/{destination}"
            )
