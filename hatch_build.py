"""Bundle the compiled extension, authoring assets and git-repo in PTk distributions."""

import importlib.util
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

GIT_REPO = "_vendor/git-repo"


def git_repo_source(root):
    """The pinned git-repo commit without history: kept from an sdist, else fetched."""
    spec = importlib.util.spec_from_file_location(
        "ptk_git_repo", root / "src/ptk/resources/git_repo/__init__.py"
    )
    pinned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pinned)
    target = root / GIT_REPO
    marker = target / ".ptk-commit"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == pinned.COMMIT:
        return target
    shutil.rmtree(target, ignore_errors=True)
    with tempfile.TemporaryDirectory(prefix="ptk-git-repo-") as work:
        for args in (
            ["init", "-q", work],
            ["-C", work, "fetch", "-q", "--depth", "1", pinned.URL, pinned.COMMIT],
            ["-C", work, "archive", "-o", str(Path(work) / "src.tar"), "FETCH_HEAD"],
        ):
            result = subprocess.run(
                ["git", *args], capture_output=True, text=True, check=False
            )
            if result.returncode:
                raise ValueError(
                    f"cannot fetch git-repo {pinned.COMMIT} from {pinned.URL} "
                    f"(read access needed): {result.stderr.strip()}"
                )
        with tarfile.open(Path(work) / "src.tar") as archive:
            archive.extractall(target, filter="data")
    marker.write_text(pinned.COMMIT + "\n", encoding="utf-8")
    return target


class AuthoringBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        if version != "editable":
            build_data["force_include"][str(git_repo_source(root))] = (
                GIT_REPO
                if self.target_name == "sdist"
                else "ptk/resources/git_repo/source"
            )
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
                    "PTk release is missing its bundled Project Toolkit VSIX"
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
