"""ptk - project tool kit: a configuration-driven project CLI."""

from importlib.metadata import PackageNotFoundError, version

# PyPI's "ptk" is an unrelated project; the import name stays ptk.
DISTRIBUTION = "xcce_ptk"

try:
    __version__ = version(DISTRIBUTION)
except PackageNotFoundError:
    # Source imports during isolated builds precede installed package metadata.
    __version__ = "0+unknown"
