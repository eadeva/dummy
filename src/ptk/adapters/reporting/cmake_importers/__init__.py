"""The two shipped, version-selected CMake evidence importers."""

from .v3 import CMake32Importer
from .v4 import CMake41Importer


def select(version):
    if version >= (4, 1, 0):
        return CMake41Importer()
    if version >= (3, 2, 0):
        return CMake32Importer()
    raise ValueError("CMake reporting requires version 3.2 or newer")
