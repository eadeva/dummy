VS Code extension and offline authoring
===========================================

Project Toolkit extension
-----------------------------

The ``project-toolkit`` extension in ``extensions/project-toolkit`` provides a
sidebar for jobs, workflows, built-in commands, variants and configuration files.
Run ``ptk self-service extension`` to install the VSIX bundled with the Python package,
then open a trusted PTK
repository or VMR. PTK must be installed on the workspace host and support
``ptk describe --json --configuration``. The extension requires VS Code 1.96 or newer.

Both installers run extension setup automatically when ``code`` is available.
Use ``install.ps1 -NoExtension`` or ``install.sh --no-extension`` to skip it.
The setup command works outside projects and with broken configuration, and is
available to every user. It is separate from maintainer-only ``maintainer sync``,
which writes shared project tasks and skills.

Use ``--code code-insiders`` (or an absolute launcher path) for another VS Code
installation and ``--profile NAME`` to choose a VS Code profile. The command
keeps an equal/newer installed extension; ``--force`` explicitly reinstalls or
downgrades it. A retained newer extension still checks PTK's JSON interface when
it loads. ``--output PATH`` exports the VSIX without starting VS Code and refuses
to overwrite existing files. VSIX installations do not automatically follow
Python upgrades: rerun the installer or ``ptk self-service extension`` after upgrading
PTK. In remote workspaces run setup on the workspace host.

Hover over a job to see Run, Dry Run, **Run Job or Workflow with Options** (gear) and
**Show Help** (question mark), each with a tooltip. The gear opens the run-options form for jobs and workflows. Jobs offer multiple
variant checkboxes, ``--only-step``/``--to`` step dropdowns in authored order, and
parameter overrides with help, defaults and declared choices. Step titles label
the dropdown choices. **More run options** exposes feature overrides, per-step
arguments and flags, with suggestions where PTK supplies them. ``--env`` requires
**Dry run**. Repository workflows offer multiple owner variants and their help text;
PTK resolves the mapped jobs' variants. Workspace workflows have no owner-variant
selector. Required non-secret job parameters open the form automatically. Help shows
the job's ``--help`` without running it or asking for parameters.
Dry Run calls ``ptk JOB --dry-run`` or ``ptk workflow run --dry-run NAME`` and shows the
planned steps without executing them.
Provide secrets through their configured environment variables. Tasks execute
PTK as a process and show output in the task terminal. Saved tasks preserve
dry-run mode, parameters, variants, run options and help requests. The extension
rechecks current choices before launching; removed steps or variants require a new selection.

Expand **Built-in commands** to browse ``self-service``, ``maintainer``, ``help`` and
other permitted commands. Duplicate ``run`` and ``report`` branches,
including workflow equivalents, are omitted in favour of job/workflow actions.
The remaining tree commands have Run, Options and Help icons. Required
arguments are prompted automatically; the gear lets you supply optional values.
Credential values and vault passwords stay in PTK's hidden terminal prompts.
**CLI help** displays ``ptk --help``; **help** opens PTK's HTML help.
The command tree requires a supported PTK inventory; incompatible inventories
show an update error. See :ref:`extension-compatibility`.

Expand a job to check one or more variants. Run, Dry Run, Clean and Re-run launch
the selected variants in parallel, with a separate named task and terminal for
each. The parameter form opens once: explicit overrides apply to all selected
variants; omitted values and template defaults resolve separately at runtime.
Canceling the form starts nothing. Open Report opens each selected variant's report.
Rerunning a task preserves its explicit variant even if the tree selection changes.
The task picker lists selected variants separately; a hand-written task without
a variant uses the project default. Repository workflows also support multiple owner variants, each in a separate task.
The choice is stored independently per job/workflow in VS Code's workspace state.
**All variants** selects every concrete variant. Unchecking the last selected
variant checks the actual configured default variant automatically; there is no
separate default checkbox. Abstract variants are excluded. This updates only the
affected tree branch, without running PTK or rewriting configuration.
Workflows use the selected owner variant and its repository variant mappings. Use **Display Variant**
for resolved features and the report icon on a job or workflow to open its report.

The configuration form uses compact rows for labels, values and actions, with a
vertical layout in narrow editor columns. Hover a field label or its **?** button
for help, or activate **?** to expand the explanation, default and constraints.
Help is supplied by the installed PTK's schema, generated from Pydantic field
descriptions. The optional-field selector shows the same help before insertion.
Open help survives save replies, and typing retains the existing deferred-save
behavior. Compatible additions to PTK's field descriptions appear after refresh.

Tree and form place scalar fields before objects and lists. At the root, scalar
metadata is followed by repository/project identity, variants and components,
jobs and workflows, execution settings, tools and credentials, artifacts and
versioning, then output settings. PTK exports explicit field-order metadata;
JSON key sorting cannot change the display order. Optional-field choices follow
the same rules. Lists keep their authored order. Jobs and workflows show dependency
trees supplied by PTK in execution direction: prerequisites first, with dependents
nested underneath. Steps with no prerequisites are roots. Shared nodes expand
once; later occurrences
are leaf references marked **shared — shown above**. Activating either occurrence
edits the same definition. Workflow nodes show their job target, including the
repository qualifier when configured, and omit redundant target labels. Joins
list **needs all** with every prerequisite, including those on other branches.
Each occurrence has its own tree identity,
so collapsing one branch does not affect another. The form provides the node's
fields; dependency branches contain dependents, not scalar field lists. Independent
branches can overlap; the tree is not a serial timeline.
Display ordering does not reorder YAML source files.

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
checks and writes ``extensions/project-toolkit/project-toolkit-0.15.0.vsix``.
Use ``ptk self-service extension --dry-run`` to preview it. Node.js and npm must be on PATH.
Set ``PTK_TEST_PYTHON`` to the project's Python interpreter to include real CLI
integration tests. CX builds downloadable VSIX artifacts on Linux and Windows;
Marketplace publication is separate. See the extension README for installation,
settings and manual smoke-test instructions.

.. _extension-compatibility:

PTK and extension compatibility
-------------------------------

PTK defines the capabilities; the extension presents them. The extension depends
on PTK's versioned JSON interface and CLI behavior, not only on its configuration
schema. It starts the configured PTK executable on the workspace host; it does
not import Python modules or require an exact Python-package release version.
Discovery calls::

   ptk describe --json --configuration

.. list-table:: Responsibilities at the integration boundary
   :header-rows: 1
   :widths: 45 55

   * - PTK supplies or performs
     - The extension uses it for
   * - Loaded values, document ownership, source locations and fingerprints
     - The logical configuration tree and edits to the correct YAML files
   * - Schemas, defaults, descriptions, constraints and field-order metadata
     - Generic forms, required-item initialization and field help
   * - Jobs, workflows, variants, parameters and permitted built-in commands
     - Available actions, variant selection and parameter forms
   * - Invocation directory, repository prefix and command paths
     - Launching PTK through VS Code tasks without a config-file override
   * - Run and built-in argument/option metadata, choices and descriptions
     - Step dropdowns, parameter help and value suggestions
   * - Validated graph nodes, prerequisites and ordered tree projection
     - Configuration navigation for job steps and workflow invocations
   * - Validation diagnostics and template-variable metadata
     - Errors, variable suggestions and field-specific insertion rules

PTK owns discovery, configuration assembly, full validation, permissions and job
or workflow execution. The extension writes YAML using PTK's ownership mappings,
then reloads through PTK. Its form checks assist editing; they do not replace
PTK's full validation. The bundled schema is not a runtime fallback.

Compatible additions
~~~~~~~~~~~~~~~~~~~~~

After refresh, the existing extension can recognize new jobs, workflows,
variants, supported parameter types, configuration fields and permitted built-in
commands exposed through the existing inventory structures. New defaults,
choices, descriptions and supported constraints need no extension rebuild.
For example, an optional integer ``timeout`` field with a default and description
can be offered by the form as a numeric input with help. Adding fields does not
migrate existing YAML; new required values can still require user edits.

PTK's internal loading implementation can also change independently, provided
the exported values, schemas, ownership mappings and command behavior preserve
the contract. New Python code alone does not require a new extension release.

Compatibility limits and versioning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The extension supports a defined set of schema constructs and parameter types,
not every possible JSON Schema feature. A new widget, unsupported schema
construct, parameter type or specialized action can require extension changes.
Although PTK supplies execution paths, dedicated actions still use known CLI
operations and flags, including validation, reports, initialization,
``--variant``, ``--dry-run``, ``--param``, ``--clean`` and ``--re-run``.
Changing those semantics can break compatibility even if the schema is unchanged.

The extension requires inventory ``schema_version: 4`` and per-project
``configuration.version: 5``. These are interface versions, separate from the
PTK package version, extension version and project marker's ``schema_version``.
Unsupported interface versions or malformed inventories are rejected with an
error; there is no legacy parser or schema fallback.

When evolving PTK, keep compatible additions within the supported contract.
Treat removal or reinterpretation of required metadata, command semantics or
editing mappings as a breaking change: update the affected interface version,
extension and integration tests together. An unchanged version number alone
does not guarantee compatibility. The recent CLI reorganization required an
inventory-version and extension update because command routing changed.

Bundling the VSIX in PTK distributes a tested pair; it does not require both
projects to have matching release numbers. Use the installers or
``ptk self-service extension`` to apply the bundled extension when needed.

Developing PTK locally
----------------------

The existing checkout installation still works::

   # PowerShell, at the repository root
   .\install\install.ps1

   # Bash
   sh install/install.sh

It rebuilds the wheel and bundled VSIX from this checkout, reinstalls PTK and
refreshes even a same-version extension. Node.js 22+ and npm are needed for this
source build. Reload the VS Code window after installation. ``-ForceExtension``
or ``--force-extension`` requests the same behaviour for explicit ``PTK_SOURCE``
overrides. The installers' Python source installation still explicitly
reinstalls the selected source; it is not a general package downgrade guard.

For the fast Python edit/test loop, run ``uv sync`` once, then ``uv run ptk ...``.
Python edits take effect immediately in the editable environment. In the
extension settings, use the absolute path to this checkout's
``.venv/Scripts/ptk.exe`` (Windows) or ``.venv/bin/ptk`` (Linux), so projects
opened elsewhere also use the development CLI. Run ``uv sync`` again when
dependencies change.

For extension changes, open ``extensions/project-toolkit`` as a VS Code folder,
run ``npm ci --include=dev`` once and press F5. The included launch configuration
builds the extension and starts an Extension Development Host. Open a test
project there and point it at the development CLI as above. After editing
JavaScript, run ``npm run build`` and reload the development window.

To install a development build into your normal VS Code instead::

   uv run ptk extension
   uv run ptk self-service extension --vsix extensions/project-toolkit/project-toolkit-0.15.0.vsix --force

Editable installs intentionally contain no built-in VSIX; supply ``--vsix`` for
this workflow. Full ``uv run ptk package`` builds the release artifacts containing
the extension. This keeps local testing independent of publishing or version bumps.

Variable insertion
------------------

Template-capable configuration text inputs offer **Insert variable…** and
autocomplete when typing ``${``. Search by name, group or description; use
arrow keys and Enter to select, or Escape to close. Insertion preserves the
surrounding text, cursor and unsaved draft and does not reload configuration.
The installed PTK supplies the catalogue, field capabilities and current job's
parameter names. Runtime availability is described rather than evaluated in
the editor. Environment and credential values are never previewed.
The catalogue follows the compatibility contract in :ref:`extension-compatibility`.

Generated tasks and offline resources
-----------------------------------------

Run ``ptk maintainer sync tasks`` to generate VS Code tasks. Run
``ptk maintainer sync agent`` for
the PTK expert agent, its skills and their reference files. ``ptk maintainer sync agent --check`` checks drift
without writing (exit code 1 when an update is needed).

Editor setup and all its subcommands are maintainer-only, including ``--check``.
They are hidden from normal users and refuse direct invocation. Maintainers are
listed by login ID in the configuration folder's ``maintainers.ptk.yml``; see
:doc:`/guides/configuration`. Generate shared tasks with ``--users-only`` so they exclude
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
commands, prefixed with ``maintainer`` for restricted targets, so a shared name never triggers an interactive choice in an editor task.
At a VMR root, ``ptk maintainer sync tasks`` includes workspace-owned workflows and
qualified member workflows and each member's tasks. Use
``ptk maintainer sync agent`` separately for member authoring resources.
VMR tasks run from the workspace root. See :doc:`/guides/workflows` for
parallelism, repository selection and CX restrictions.

Workspace editor commands require membership in the VMR root's own
``maintainers.ptk.yml``. Commands updating member repositories also require
membership in each target's list; synchronization checks every member before any
write. Use ``ptk ALIAS maintainer sync tasks`` or ``ptk ALIAS maintainer sync agent`` to update only a repository you maintain.

Report files
------------

Jobs and workflows print the report file path. PTK does not start a local HTTP
server or print browser URLs. Click **Open Latest Job or Workflow Report** on the
job/workflow row. Job reports follow the selected variant; workflows open the
latest saved aggregate report. Missing reports produce an informational message
in the task terminal, without running anything. Saved tasks with ``report: true``
remain report requests when rerun.

The CLI operations are
``ptk report open --if-exists JOB`` and ``ptk report open --workflow NAME --if-exists``.
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
available even without a project, when it offers ``ptk init``. Use Raw YAML
for aliases or values that the form cannot safely represent.

The job parameter gear opens a single window with help, default values, text
fields, checkboxes and choices. Only enabled overrides are passed to PTK;
environment values and template defaults are resolved by PTK at execution time.
Required non-secret parameters open this form automatically. Use Run job or Dry
run to submit it, or Cancel to leave without executing. Secret parameters are
not exposed in this window.
