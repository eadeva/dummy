"""git-repo (Apache-2.0, XC-CE fork) shipped with ptk.

The launcher ``repo`` is kept here; packaging (hatch_build.py) adds the source of COMMIT
without Git history as ``source/``, so installed ptk needs no access to the fork.
"""

URL = "https://github.boschdevcloud.com/XC-CE/git-repo"
COMMIT = "1d18f02c006a987b7d7530601afcddd26a11eee5"
# git describe of COMMIT
VERSION = "v2.61.1-9-g1d18f02"
