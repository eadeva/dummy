"""ptk - project tool kit: a configuration-driven project CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ptk")
except PackageNotFoundError:
    # Source imports during isolated builds precede installed package metadata.
    __version__ = "0+unknown"
