VS Code setup and offline authoring
=====================================

Run ``ptk setup vscode`` to generate VS Code tasks and install PTK's project-facing
skills. In a VMR, qualify the repository: ``ptk ALIAS setup vscode``.
Use ``ptk setup vscode tasks`` for tasks only, or ``ptk setup vscode skills`` for
skills and their reference files. ``ptk setup vscode skills --check`` checks drift
without writing (exit code 1 when an update is needed).

Fourteen project skills are installed under ``.github/skills/ptk-*/SKILL.md``.
Version-matched documentation, examples and the generated configuration schema
live under ``.github/ptk``. Skill links are relative to their own SKILL.md files;
the consuming repository needs neither PTK's source tree nor network access.
The PTK-development and PTK-documentation-maintenance skills stay in the PTK
source repository, because they operate on PTK itself.

The wheel contains lightweight readable documentation sources; Sphinx is not a
runtime dependency. ``.github/ptk/config-schema.json`` provides the exact field
reference. Full rendered HTML is a separate release artifact. Docs and examples
are reference material: edit the consuming repository's own configuration and
copy examples to a temporary directory before running them.

Setup records hashes and the PTK version in ``.github/ptk/manifest.json``. It
updates unchanged managed files and removes obsolete unchanged managed files.
Custom skills and other GitHub files are preserved. Locally modified or conflicting
files cause an error before writing; reconcile them explicitly and rerun setup.
Checks and writes refuse symlinked managed paths. Commit the generated skills,
reference files and manifest together if the team should share them.

Local workflows
---------------

Workflow tasks call ``ptk workflow run NAME`` on the local machine; they do not
invoke GitHub Actions. Repository task files include actions and local workflows.
At a VMR root, ``ptk setup vscode tasks`` includes workspace-owned workflows and
qualified member workflows. ``ptk setup vscode`` also installs each member's
skills/tasks. VMR tasks run from the workspace root. See :doc:`workflows` for
parallelism, repository selection and CX restrictions.
