Development and verification
============================

Architecture
------------

Dependencies point inward: drivers call application use cases; adapters implement
application ports; the domain contains models and pure rules. Wire adapters in
``src/ptk/bootstrap.py``. Keep filesystem and process access out of the domain.

Local checks
------------

Run from the repository root::

   uv sync --group docs
   uv run pytest
   uv run ruff check
   uv run ruff format --check
   uv run sphinx-build -W --keep-going -b html docs docs/_build/html

The documentation build treats warnings as errors. The quickstart configuration
and script are included from their original files; the tests run that same example
for both variants in a directory containing spaces.

Continuous integration
----------------------

GitHub Actions runs the test suite on Ubuntu and Windows with Python 3.12 and
3.13. Linux also runs lint, formatting and the documentation build. Existing
POSIX-only tests remain skipped on Windows; the quickstart integration tests
exercise actual Python processes and report generation on both platforms.
A green Linux run alone does not establish that Windows works.

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
