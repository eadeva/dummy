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
invoke GitHub Actions. Repository task files include jobs and local workflows.
Generated tasks use explicit ``ptk run JOB`` and ``ptk workflow run WORKFLOW``
commands, so a shared name never triggers an interactive choice in an editor task.
At a VMR root, ``ptk setup vscode tasks`` includes workspace-owned workflows and
qualified member workflows. ``ptk setup vscode`` also installs each member's
skills/tasks. VMR tasks run from the workspace root. See :doc:`workflows` for
parallelism, repository selection and CX restrictions.

Browser links in the terminal
-----------------------------

In an interactive local VS Code terminal, job and workflow reports print a
``browser: http://127.0.0.1:...`` link alongside their file path. Ctrl+click
(Cmd+click on macOS) opens the rendered report. ``ptk report open`` prints the
same kind of link. Plain file paths and ``file://`` links normally open in VS
Code's editor instead.

To use the operating system's default browser in current VS Code versions, add
this to VS Code's settings::

   "workbench.browser.openLocalhostLinks": false

See the `VS Code browser documentation
<https://code.visualstudio.com/docs/debugtest/integrated-browser#_use-an-external-browser>`_.
PTK does not overwrite your editor settings.

The link uses a reusable loopback-only helper for that repository, with a random
URL token. It serves registered report folders and their log files, without
directory listings. It survives the CLI command and exits after an hour without
requests. After expiry, run the report command again for a fresh link. File
reports remain available permanently. No helper starts on CX, for redirected
output, or outside VS Code; automatic report opening remains a separate policy.
Remote VS Code sessions require port forwarding to the machine running PTK.
