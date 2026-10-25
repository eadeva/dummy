"""Use PTK's configured project version for all Python distribution builds."""

import os
import sys
from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


class PTKMetadataHook(MetadataHookInterface):
    def update(self, metadata):
        # Build isolation has the small config-engine dependency set, not PTK
        # itself. Read this checkout's implementation without bootstrapping its CLI.
        sys.path.insert(0, str(Path(self.root) / "src"))
        try:
            from ptk.package_version import package_version

            metadata["version"] = package_version(
                Path(self.root), resolved_version=os.environ.get("_PTK_BUILD_VERSION")
            )
        finally:
            sys.path.pop(0)
