CI/CD and release preparation
=============================

The checked-in ``.github/workflows/ci.yml`` is the authoritative CI definition.
It runs PTK's configured jobs; PTK's local workflow executor is not a CI service.
Local workflows reject CI execution. CI orchestration remains in the host's
pipeline definition.

Verification pipeline
---------------------

.. list-table:: Current GitHub Actions jobs
   :header-rows: 1
   :widths: 20 25 55

   * - Job
     - Matrix
     - Checks and artifacts
   * - ``tests``
     - Ubuntu / Windows; Python 3.12, 3.13, 3.14
     - Sync development dependencies, verify CMake, run ``ptk test``; benchmark CLI startup on Python 3.12.
   * - ``quality``
     - Ubuntu; Python 3.12
     - Validate generated configuration, run hooks, Ruff and documentation, then inspect HTML reports and editor pages with Chromium.
   * - ``vscode-extension``
     - Ubuntu / Windows; Python 3.12; Node.js 22
     - Run the extension build/test job and upload its VSIX as a CI artifact.
   * - ``package``
     - Ubuntu / Windows; Python 3.12; Node.js 22
     - Test package builds and run ``ptk package`` with release and documentation dependencies.

The matrix is intended coverage, not evidence that every host has passed on every
commit. Native Windows checks must run on Windows. Conditional skips and missing
optional host tools are reported by the test suite. A local Linux pass does not
establish Windows support by itself.

Running the checks locally
--------------------------

From PTK's source checkout::

   uv sync --group docs --group release
   uv run ptk validate --generated
   uv run ptk pre-commit run --all-files --show-diff-on-failure
   uv run ptk test
   uv run ptk check
   uv run ptk docs
   uv run ptk package

These are PTK's own configured jobs, not commands automatically available in
all consuming projects. See :doc:`/guides/development` for test prerequisites
and selecting individual tests. The documentation job builds RST with warnings
as errors. Requirements checks verify identifiers, mandatory attributes,
relationship targets and the existence of cited implementation/test files.
They do not certify that a requirement has been accepted or verified on all
supported platforms.

Package and release boundary
----------------------------

``ptk package`` stages a wheel, source distribution, matching VSIX, HTML docs
and a manifest after checks. It builds the wheel from the source distribution
and exercises the installed CLI in a separate project. Git-derived package
version metadata is frozen into the source distribution so a consumer can
rebuild it without repository history. See :doc:`/guides/packaging`.

Preparation does **not** publish to a Python index, upload releases, create tags
or install a package for teammates. Those operations require the team's release
process. The supplied installer selects a Python package source, installs PTK
for the current user, and invokes its completion/editor setup. Consumers need
neither Node.js nor Sphinx to run a prepared package.

Future pipeline generation
--------------------------

Generating GitHub workflow files from PTK configuration is a draft roadmap item,
not a supported command. It is recorded as :need:`REQ_Sw_CI_GENERATION` rather
than described as part of the current release pipeline.
