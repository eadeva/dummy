"""Sphinx configuration; build with warnings treated as errors."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "_ext"))

project = "ptk"
author = "ptk contributors"
extensions = ["schema_reference"]
exclude_patterns = ["_build", "PLAN.md"]
html_theme = "alabaster"
