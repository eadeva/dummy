VS Code extension and offline authoring
===========================================

Project Toolkit extension
-----------------------------

The ``project-toolkit`` extension in ``extensions/project-toolkit`` provides a
sidebar for jobs, workflows, built-in commands, variants and configuration files. Install the VSIX
using VS Code's **Extensions: Install from VSIX...**, then open a trusted PTK
repository or VMR. PTK must be installed on the workspace host and support
``ptk describe --json``. The extension requires VS Code 1.96 or newer.

Hover over a job to see Run, Dry Run, **Run Job with Parameters** (gear) and
**Show Help** (question mark), each with a tooltip. The gear prompts for optional
overrides; required non-secret parameters are prompted automatically. Help shows
the job's ``--help`` without running it or asking for parameters.
Dry Run calls ``ptk dry-run JOB`` or ``ptk workflow dry-run NAME`` and shows the
planned steps without executing them.
Provide secrets through their configured environment variables. Tasks execute
PTK as a process and show output in the task terminal. Saved tasks preserve
dry-run mode, parameters, variants and help requests.

Expand **Built-in commands** to browse ``setup``, ``setup creds``, ``help`` and
other permitted commands. The tree has Run, Options and Help icons. Required
arguments are prompted automatically; the gear lets you supply optional values.
Credential values and vault passwords stay in PTK's hidden terminal prompts.
**CLI help** displays ``ptk --help``; **help** opens PTK's HTML help.
Update PTK from the same checkout to expose the command tree. Older inventories
retain job actions and CLI help, with an update hint for built-in browsing.

Selecting a variant stores the choice in VS Code's workspace state for that
repository. **Use project default** clears it. Selection never rewrites PTK YAML.
Workflows keep their authored per-job variant selections. Use **Display Variant**
for resolved features and **Open Latest Job Report** for PTK's report links.

Multiple folders, VMR members and workspace workflows are supported. Discovery
uses PTK's role-filtered inventory; commands still enforce permissions in the CLI.
Configuration changes trigger a refresh. Errors appear on project nodes and in
the Project Toolkit output channel. Discovery can load project plugins, so the
extension requires workspace trust.

Set ``projectToolkit.executable`` to a program or absolute path and
``projectToolkit.arguments`` to separate prefix arguments. For uv, use executable
``uv`` and arguments ``["run", "ptk"]``. Use an installed PTK executable at VMR
roots without a uv project. SSH/WSL/container sessions run PTK on their workspace
host. Increase ``projectToolkit.discoveryTimeout`` for slow discovery.

Build from the repository root with ``ptk extension`` or ``uv run ptk extension``.
The job checks Node.js 22+ and npm, installs the build dependencies, runs the
checks and writes ``extensions/project-toolkit/project-toolkit-0.2.1.vsix``.
Use ``ptk dry-run extension`` to preview it. Node.js and npm must be on PATH.
Set ``PTK_TEST_PYTHON`` to the project's Python interpreter to include real CLI
integration tests. CI builds downloadable VSIX artifacts on Linux and Windows;
Marketplace publication is separate. See the extension README for installation,
settings and manual smoke-test instructions.

Generated tasks and offline resources
-----------------------------------------

Run ``ptk setup vscode`` to generate VS Code tasks and install PTK's project-facing
skills. In a VMR, qualify the repository: ``ptk ALIAS setup vscode``.
Use ``ptk setup vscode tasks`` for tasks only, or ``ptk setup vscode skills`` for
skills and their reference files. ``ptk setup vscode skills --check`` checks drift
without writing (exit code 1 when an update is needed).

Editor setup and all its subcommands are maintainer-only, including ``--check``.
They are hidden from normal users and refuse direct invocation. Maintainers are
listed by login ID in the configuration folder's ``maintainers.ptk.yml``; see
:doc:`configuration`. Generate shared tasks with ``--users-only`` so they exclude
maintainer jobs and workflows. Running existing tasks remains available to users.

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
-------------------

Workflow tasks call ``ptk workflow run NAME`` on the local machine; they do not
invoke GitHub Actions. Repository task files include jobs and local workflows.
Generated tasks use explicit ``ptk run JOB`` and ``ptk workflow run WORKFLOW``
commands, so a shared name never triggers an interactive choice in an editor task.
At a VMR root, ``ptk setup vscode tasks`` includes workspace-owned workflows and
qualified member workflows. ``ptk setup vscode`` also installs each member's
skills/tasks. VMR tasks run from the workspace root. See :doc:`workflows` for
parallelism, repository selection and CX restrictions.

Workspace editor commands require membership in the VMR root's own
``maintainers.ptk.yml``. Commands updating member repositories also require
membership in each target's list; combined setup checks every member before any
write. Use ``ptk ALIAS setup vscode`` to update only a repository you maintain.

Browser links in the terminal
---------------------------------

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
