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
``config/ptk`` with a ``default`` variant and no components::

   uv sync
   uv run ptk validate
   uv run ptk test
   uv run ptk check
   uv run ptk docs
   uv run ptk package

Build the VS Code extension with ``uv run ptk extension`` (or ``ptk extension``
with an installed CLI). This job needs Node.js 22+ and npm on PATH. It installs
locked npm dependencies, runs extension checks and creates the VSIX under
``extensions/project-toolkit``. ``ptk extension --dry-run`` previews its steps.

An installed ``ptk`` can run the same jobs without the ``uv run`` prefix.
Jobs using a Python runtime always select this checkout's uv project, with
separate environments under ``.ptk/venvs/<job>``. This prevents a job from
synchronizing the checkout's ``.venv`` while PTK or an editor is using it.
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
``_builds/default/docs/sphinx/html/index.html``. The default job is ``test``; the dummy hello
and header-generation jobs are not part of this repository configuration.

``check`` runs Ruff lint and format checks without modifying files. To apply
formatting intentionally, use ``uv run ruff format``. The test job explicitly
inherits caller PATH to exercise installed host tools; ordinary environment
variables remain filtered.

This repository enables pre-commit through ``config/ptk/configs.ptk.yml``.
Local jobs/workflows automatically install or repair the hooks. The committed
``.pre-commit-config.yaml`` combines PTK's base with its repository overlay;
Ruff uses the existing ``pyproject.toml`` settings. Run
``uv run ptk pre-commit run --all-files`` to check the whole checkout. The CI quality
job runs those hooks and checks that the generated configuration is current.
PTK-run hooks clear caller Python environment selectors such as ``VIRTUAL_ENV``
and ``UV_PROJECT_ENVIRONMENT`` and remove PTK's own virtualenv bin directory
from the hook PATH. This prevents inherited settings from redirecting a hook's
``uv sync`` into PTK's installation. Index, proxy, certificate and cache settings
are retained. Hooks should declare their required runtime/dependencies.
After changing the overlay, a maintainer runs
``ptk maintainer sync configs pre-commit`` and commits both files.

Package builds and job runs use the same Git-managed PTK version configuration.
Reachable ``v*`` tags take precedence; untagged/shallow checkouts use the explicit
development fallback in ``versioning.ptk.yml``. Source distributions freeze their
resolved version in metadata, so rebuilding them does not require Git.
Neither tests nor documentation builds require a release tag.
uv's editable-build cache tracks Git commits/tags and version configuration.
The installed CLI reports its installation version; reinstall after other local
edits when needed with ``uv sync --reinstall-package ptk``. Package preparation
always uses the newly resolved job snapshot.

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

``tests/test_workspace_init.py`` exercises empty and mixed VMRs, invocation from
member subdirectories, manual member lists, missing checkouts, alias collisions,
single-directory targeting, required config-folder input and one-time prompting.
Filesystem snapshots verify
that previews, repeated initialization and preflight failures preserve existing
configuration, while generated member jobs run through the real CLI.

Documentation and skills
------------------------

The documentation environment pins Sphinx 9.1.0, Sphinx-Needs 8.5.0, the
Read the Docs theme 3.1.0 and Sphinx-Design 0.7.0. Sphinx-Design supplies
RST grids and cards; repository-owned SVGs provide diagrams without a network
renderer. Requirement overview counts come from Sphinx-Needs filters. Keep
documentation authoring conventions separate from PTK product requirements.

The configuration reference is generated from the validation schema and uses
YAML paths and values. Published docs do not include a source-module catalog or
Python API reference. Plugin-authoring contracts live with the plugin-development
skill and are available to installed assistants outside the published docs.

Seventeen repository-local authoring skills are shipped under ``.claude/skills`` and
included in the documentation. Tests check catalog completeness and source links.
The wheel bundles fifteen project-facing skills, reference docs and examples
through the allowlist in ``src/ptk/authoring_bundle.py``. Keep the canonical skill
files in ``.claude/skills``; do not maintain another copy for installed users.
Consumer skill instructions must not depend on PTK's ``src`` or ``tests`` folders.

``ptk package`` selects the release/docs groups, builds the wheel from an sdist,
checks metadata, and smoke-tests an installed wheel in a separate project before
staging artifacts. Linux and Windows packaging jobs run this same job. The
wheel smoke test reuses installed runtime dependencies, with no dependency fetch
or upload. See :doc:`/guides/packaging` for artifact layout and :doc:`/guides/editor` for offline
resources and protected upgrades.

Native Windows tests cover batch files, PowerShell, timeouts and cancellation.
Chocolatey command construction and administrator checks use a fake runner on
both platforms; CI does not perform real machine-wide Chocolatey installations.

``tests/hooks`` uses real temporary Git repositories and the dev group's
pre-commit hook installation. A local hook demonstrates that a failing check blocks
a real commit. Tests cover gitfiles, symlinks, linked worktrees, custom output
paths, preserved hooks, broken runtimes, concurrent installation and VMR workflow
preflight. Package acquisition is replaced in those tests; no remote hook repos
are downloaded. Help and preview tests guard the absence of installation work.

Acceptance boundaries
---------------------

The VS Code extension's ``npm run package`` runs JavaScript syntax checks and
Node tests, then packages a VSIX. ``PTK_TEST_PYTHON`` enables integration tests
which invoke the real CLI from Node for repository and VMR discovery, previews,
parameter passing and execution. The extension CI job runs ``uv run ptk extension``
on Linux and Windows and uploads the VSIX. Controller tests use an injected VS Code API; graphical
extension-host acceptance remains a manual check. See :doc:`/guides/editor`.

Plugin selection and generators are documented in :doc:`/reference/plugins`; variant inspection
and matrix commands in :doc:`/reference/cli`; background process behavior in :doc:`/reference/execution`.
Real machine-wide tool/credential setup still needs acceptance on target machines.
Publishing and merging are separate decisions.

Startup performance
-------------------

Run ``uv run python scripts/benchmark_cli.py --output .ptk/benchmark-cli.json``
for repeated process-start measurements on this checkout and temporary VMR
fixtures. See :doc:`/guides/performance` for methodology, measured results and profiling.
The Python 3.12 Linux/Windows CI jobs also run this benchmark and print their
results; timings are evidence, not pass/fail thresholds on shared runners.

Keep application services lazy: ``App`` constructs execution, tools, credentials,
editor resources and reports only on first use. Explicitly selected plugins still
load for validation. CLI state caches both successful loads and expected errors
for one invocation; do not turn these into process-global or disk caches. Tests
bound load/identity/diagnostic-path work and check fresh subprocess imports.
