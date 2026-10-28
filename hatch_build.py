"""Bundle the compiled extension and authoring assets in PTK distributions."""

import importlib.util
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class AuthoringBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        if version != "editable":
            spec = importlib.util.spec_from_file_location(
                "ptk_extension_bundle", root / "src/ptk/extension_bundle.py"
            )
            bundle = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bundle)
            vsix = root / "src/ptk" / bundle.RESOURCE
            if (root / "extensions/project-toolkit/package.json").is_file():
                self._extension_work = tempfile.TemporaryDirectory(prefix="ptk-vsix-")
                vsix = Path(self._extension_work.name) / "project-toolkit.vsix"
                bundle.build_vsix(root, vsix)
            if not vsix.is_file():
                raise ValueError(
                    "PTK release is missing its bundled Project Toolkit VSIX"
                )
            bundle.inspect_vsix(vsix)
            prefix = "src/ptk/" if self.target_name == "sdist" else "ptk/"
            build_data["force_include"][str(vsix)] = prefix + bundle.RESOURCE
        if self.target_name != "wheel":
            return
        spec = importlib.util.spec_from_file_location(
            "ptk_authoring_bundle", root / "src/ptk/authoring_bundle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for destination, source in module.source_files(root).items():
            build_data["force_include"][str(source)] = (
                f"ptk/resources/authoring/{destination}"
            )

    def finalize(self, version, build_data, artifact_path):
        if hasattr(self, "_extension_work"):
            self._extension_work.cleanup()
