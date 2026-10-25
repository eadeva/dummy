Development and verification
============================

Architecture
------------

Dependencies point inward: drivers call application use cases; adapters implement
application ports; the domain contains models and pure rules. Wire adapters in
``src/ptk/bootstrap.py``. Keep filesystem and process access out of the domain.

Local checks
------------

Run from the repository root; the project uses its own PTK configuration in
``config/ptk`` with one ``default`` variant and no components::

   uv sync
   uv run ptk setup config validate
   uv run ptk test
   uv run ptk check
   uv run ptk docs

An installed ``ptk`` can run the same actions without the ``uv run`` prefix.
The action's Python runtime always selects this checkout's uv project.
``test`` and ``check`` select its ``dev`` dependency group; ``docs`` selects
``docs``, installing missing dependencies as needed. Groups remain defined in
``pyproject.toml`` rather than duplicated in PTK tool definitions.

The ``dev`` group includes pinned CMake for the native generator integration
test. uv puts the project's executables first on PATH, so a host CMake launcher
from another Python installation cannot shadow this dependency. CMake is
installed inside the project environment; no machine-wide installation is needed.

``ptk test -- tests/test_init.py -q`` selects tests and forwards pytest options.
JUnit results go to ``_reports/default/test/pytest/pytest.xml`` and are included
in PTK's report, even when pytest fails. HTML docs go to
``_builds/default/docs/sphinx/html/index.html``. The default action is ``test``; the dummy hello
and header-generation actions are not part of this repository configuration.

``check`` runs Ruff lint and format checks without modifying files. To apply
formatting intentionally, use ``uv run ruff format``. The test action explicitly
inherits caller PATH to exercise installed host tools; ordinary environment
variables remain filtered. DISPLAY/XAUTHORITY are kept for optional GUI tests.

Version discovery uses reachable ``v*`` Git tags, falling back to the package
version in ``pyproject.toml`` for untagged, shallow or source-only checkouts.
Neither tests nor documentation builds require a release tag.

The documentation build treats warnings as errors. The quickstart configuration
and script are included from their original files; the tests run that same example
for both variants in a directory containing spaces.

Continuous integration
----------------------

GitHub Actions runs the test suite on Ubuntu and Windows with Python 3.12, 3.13
and 3.14. CI checks the project's CMake with ``uv run cmake --version``. The
generated CMake integration test requires that dependency and cannot silently
skip. CI calls ``ptk test``, ``ptk check`` and ``ptk docs`` for the same workflows used locally. Existing
POSIX-only tests remain skipped on Windows; the quickstart integration tests
exercise actual Python processes and report generation on both platforms.
A green Linux run alone does not establish that Windows works.

The demo dry-run test uses a temporary copy and checks that both fresh and
previously used workspaces remain unchanged. Tests must not assume a developer's
example folders have no previous output. Filesystem identity checks account for
Windows path capitalization. CMake integration failures report the selected
executable, its version, output and generated script to diagnose local tool issues.

VMR discovery tests use real temporary directories and relative Git pointers,
including nested paths and git-repo worktree metadata. They check that unrelated
repositories under a workspace remain standalone, missing indexes fail without
recursive scanning, and manual markers select only bounded member paths.
Read-count assertions verify per-invocation caching across routing, versioning
and credentials without timing-sensitive performance thresholds. A subsequent
CLI invocation must see changes to the member index. Symlink tests skip only
when the platform cannot create symlinks; ``gitdir:`` coverage runs everywhere.

Documentation and skills
------------------------

The configuration reference is generated from the validation models. Thirteen
repository-local authoring skills are shipped under ``.claude/skills`` and
included in the documentation. Tests check catalog completeness and source links.

Native Windows tests cover batch files, PowerShell, timeouts and cancellation.
Chocolatey command construction and administrator checks use a fake runner on
both platforms; CI does not perform real machine-wide Chocolatey installations.

Acceptance boundaries
---------------------

Plugin contracts and generators are documented in :doc:`plugins`; variant editing
and matrix commands in :doc:`cli`; background process and GUI behavior in :doc:`m11`.
The GUI CI job uses Xvfb and the real Tk event loop to test validation/export.
Native desktop appearance and real machine-wide tool/credential setup still need
acceptance on the target machines. Publishing and merging are separate decisions.
