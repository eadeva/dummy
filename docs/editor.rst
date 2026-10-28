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
other permitted commands. Duplicate ``run``, ``dry-run`` and ``report`` branches,
including workflow equivalents, are omitted in favour of job/workflow actions.
The remaining tree commands have Run, Options and Help icons. Required
arguments are prompted automatically; the gear lets you supply optional values.
Credential values and vault passwords stay in PTK's hidden terminal prompts.
**CLI help** displays ``ptk --help``; **help** opens PTK's HTML help.
Update PTK from the same checkout to expose the command tree. Older inventories
retain job actions and CLI help, with an update hint for built-in browsing.

Selecting a variant stores the choice in VS Code's workspace state for that
repository. **Use project default** clears it. Selection never rewrites PTK YAML.
Workflows use the selected owner variant and its repository variant mappings. Use **Display Variant**
for resolved features and the report icon on a job or workflow to open its report.

Multiple folders, VMR members and workspace workflows are supported. Discovery
uses PTK's role-filtered inventory; commands still enforce permissions in the CLI.
Configuration changes trigger a refresh. Errors appear on project nodes and in
the Project Toolkit output channel. Discovery can load project plugins, so the
extension requires workspace trust.

Set ``projectToolkit.executable`` to a program or absolute path and
``projectToolkit.arguments`` to separate prefix arguments. For uv, use executable
``uv`` and arguments ``["run", "--no-sync", "ptk"]``. Use an installed PTK executable at VMR
roots without a uv project. SSH/WSL/container sessions run PTK on their workspace
host. Increase ``projectToolkit.discoveryTimeout`` for slow discovery.

For a uv-managed project, prepare or update its environment with an explicit
``uv sync``. The extension inserts ``--no-sync`` into existing ``uv run`` settings
for discovery and all tasks, so launching a command does not reinstall PTK or
its dependencies. Child job runtimes can still synchronize their own environments.
Installed configuration copies in virtual environments and generated output do
not trigger discovery. Refresh requests are serialized, and PTK task completion
refreshes the tree. Click **PTK unavailable** to see the exact discovery error.

Build from the repository root with ``ptk extension`` or ``uv run ptk extension``.
The job checks Node.js 22+ and npm, installs the build dependencies, runs the
checks and writes ``extensions/project-toolkit/project-toolkit-0.7.0.vsix``.
Use ``ptk dry-run extension`` to preview it. Node.js and npm must be on PATH.
Set ``PTK_TEST_PYTHON`` to the project's Python interpreter to include real CLI
integration tests. CI builds downloadable VSIX artifacts on Linux and Windows;
Marketplace publication is separate. See the extension README for installation,
settings and manual smoke-test instructions.

Template-capable configuration text inputs offer **Insert variable…** and
autocomplete when typing ``${``. Search by name, group or description; use
arrow keys and Enter to select, or Escape to close. Insertion preserves the
surrounding text, cursor and unsaved draft and does not reload configuration.
The installed PTK supplies the catalogue, field capabilities and current job's
parameter names. Runtime availability is described rather than evaluated in
the editor. Environment and credential values are never previewed.
Update PTK and extension 0.7.0 together to use this feature.

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

Report files
------------

Jobs and workflows print the report file path. PTK does not start a local HTTP
server or print browser URLs. Click **Open Latest Job or Workflow Report** on the
job/workflow row. Job reports follow the selected variant; workflows open the
latest saved aggregate report. Missing reports produce an informational message
in the task terminal, without running anything. Saved tasks with ``report: true``
remain report requests when rerun.

Update PTK together with extension 0.3.2. The CLI operations are
``ptk report open --if-exists JOB`` and ``ptk workflow report --if-exists NAME``.
Omitting ``--if-exists`` retains an error for missing reports. Configured
``open_report`` policies continue to open reports after local runs. Remote
sessions open files on the machine running PTK.

Cleanup actions
---------------

Jobs and workflows expose **Clean Job or Workflow Outputs** (trash icon) and
**Clean Outputs and Re-run Job or Workflow** (restart icon). They use the selected
repository variant; workflow mappings are resolved by PTK. Clean does not prompt
for job parameters. Saved tasks support mutually exclusive ``clean`` and ``reRun``
booleans and can combine either with ``preview: true`` to inspect deletion paths.
The built-in command tree exposes ``clean-all`` for repositories and
``vmr-clean-all`` at the VMR root. Their confirmation occurs in the focused PTK
terminal; the Options action also exposes ``--dry-run`` and ``--yes``.

Configuration and parameter forms
---------------------------------

Configuration is a logical schema tree. Components appear with their features,
dependencies and source directory. The installed PTK supplies schemas, file ownership,
source locations and errors. New entities create their conventional file; component
features go beside their code. Raw-file forms use the appropriate document schema.

Text and numbers remain local while typing. Leaving a field, saving or navigating
commits the edit; save replies preserve focus, cursor and unfinished input.
Add actions are queued in order and acknowledge the newest completed refresh,
so file-watcher activity cannot hide a successfully added item. New items include
required descendants and minimum collection entries from PTK's schema. Workflow
steps select an existing job; create a job first if none exists.
Empty text fields have red borders and a fill-in message that clears while typing.
Zero and false remain filled values. Starter URLs use ``example.invalid`` and
must be replaced with the intended endpoint before use.
The form uses the VS Code tree and breadcrumbs for navigation. List rows show
names or values. There is no duplicate navigation sidebar or destination picker.
Theme-aware colors distinguish jobs, workflows and configuration categories.
Fingerprints reject stale edits, and dirty YAML must be saved first.

Loading errors appear in the tree and Problems panel. Validate Configuration stays
available even without a project, when it offers ``ptk setup init``. Use Raw YAML
for aliases or values that the form cannot safely represent.

The job parameter gear opens a single window with help, default values, text
fields, checkboxes and choices. Only enabled overrides are passed to PTK;
environment values and template defaults are resolved by PTK at execution time.
Required non-secret parameters open this form automatically. Use Run job or Dry
run to submit it, or Cancel to leave without executing. Secret parameters are
not exposed in this window.
