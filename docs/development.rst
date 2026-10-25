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

Scope and remaining work
------------------------

M10 is in progress. The initial documentation and runnable example are present.
The full configuration reference, the eleven authoring skills listed in
``docs/PLAN.md``, and broader native Windows coverage (batch files, PowerShell,
Chocolatey and cancellation) remain to be completed. Plugin entry-point loading
and commands listed only in the plan must not be documented as available until
implemented and tested.
