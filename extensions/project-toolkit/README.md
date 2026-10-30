# Project Toolkit

Run PTK jobs, local workflows and built-in commands from VS Code, with a project
sidebar, help, variant selection, parameter forms, a configuration editor and reports.

## Install

1. Install PTK using `install/install.ps1` or `install/install.sh`. Both install
   the extension bundled in the Python package when VS Code is available. The CLI must
   support `ptk describe --json --configuration` (inventory version 3 and configuration interface version 2).
2. If PTK was installed directly with uv, run `ptk self-service extension` afterwards.
   Alternatively, in VS Code run **Extensions: Install from VSIX...** and select
   `project-toolkit-0.12.0.vsix`. You can also use
   `code --install-extension project-toolkit-0.12.0.vsix`.
3. Open your PTK repository or VMR workspace, trust its contents, then open
   **Project Toolkit** in the activity bar.

VS Code 1.96 or newer is required. The extension runs on the workspace host;
for SSH, WSL or Dev Containers, install PTK on that host. The extension is
distributed as a VSIX, without a Marketplace publication.

`ptk self-service extension` works without a project, preserves equal/newer extension
versions, and accepts `--force` for a deliberate reinstall/downgrade,
`--profile NAME`, `--code code-insiders`, and `--output PATH` for offline export.
Rerun it after upgrading the Python package to apply the bundled extension.
For local Python edits, `uv sync` creates an editable environment; point the
extension executable at its `.venv/Scripts/ptk.exe` or `.venv/bin/ptk`.
For extension development, open this folder, run `npm ci --include=dev`, then F5.
The launch configuration builds the extension and starts a Development Host.
Rebuild and reload that window after edits. To update normal VS Code, build the
VSIX and run `uv run ptk self-service extension --vsix PATH --force` from the PTK root.

If PTK is not on the extension host's PATH, set **Project Toolkit: Executable**
to its absolute path. To use a uv-managed project, run `uv sync` in its root once
to prepare the environment, then configure:

```json
{
  "projectToolkit.executable": "uv",
  "projectToolkit.arguments": ["run", "--no-sync", "ptk"]
}
```

The extension adds `--no-sync` to existing `uv`/`uv.exe` settings beginning with
`run`, for both discovery and tasks. This prevents a version check, tree refresh,
help request or other command from reinstalling the environment that runs PTK.
Run `uv sync` explicitly after changing dependencies. Job steps can still prepare
their own Python runtimes normally; the extension does not set `UV_NO_SYNC`.

The executable setting is a program name or path, with each argument entered
separately. With a VMR, use an installed PTK executable if its root has no uv
project. Discovery errors appear in **Output > Project Toolkit** and on the
workspace node. Click a **PTK unavailable** node to show the exact error.
Set `projectToolkit.discoveryTimeout` (seconds) for slow projects.

## Compatibility with PTK

**PTK defines the capabilities; the extension presents them.** The extension
uses PTK's CLI and JSON interface, not Python imports or an exact package version.
`ptk describe --json --configuration` supplies loaded values, schemas, field help,
file ownership, diagnostics, variables, jobs, workflows, variants, parameters and
permitted command paths/options, value suggestions and invocation directory/prefix.
PTK handles loading, full validation and execution;
the extension renders the UI, writes YAML using PTK's mappings and reloads it.

Compatible additions appear after refresh without rebuilding the extension:
ordinary configuration fields, descriptions, defaults, choices, jobs, workflows,
variants and built-in commands using supported inventory/schema structures.
For example, a new optional integer field can use the existing numeric input and
help display. New required values may still need to be filled in existing YAML.

New widgets, unsupported schema constructs or parameter types, and changes to
the CLI operations used by dedicated actions can require an extension update.
Some action paths and flags are known by the extension, including validation,
reports, initialization, variants, dry runs and cleanup; the schema alone is
not the full contract.

Extension 0.12.0 requires inventory `schema_version: 3` and
`configuration.version: 2`. These are independent of package/release numbers
and the project marker's schema version. Unsupported interfaces are rejected;
there is no legacy parser or runtime schema fallback. Breaking changes must
update the affected interface version, extension and integration tests together.
The bundled VSIX provides a tested pair without requiring matching release numbers.
See the full [compatibility contract](../../docs/guides/editor.rst#ptk-and-extension-compatibility).

## Use

Template-capable configuration inputs have a **${}** button (**Insert variable…**) and autocomplete
after `${`. Search names, groups and descriptions; use arrow keys and Enter to
insert, or Escape to close. Variables insert at the cursor without saving,
reloading the form or losing unfinished text. Environment placeholders select
the name for editing. The installed PTK supplies the catalogue and tells the
form which fields support templates. Job parameters are scoped to their job;
credential references are only offered for step environment values. No resolved
environment or credential values are displayed. Compatible catalogue additions
are read from PTK after refresh.

PTK resolves `${git.branch}`, `${git.commit}`, `${git.short_commit}`, `${git.tag}`,
`${git.tags}` and `${git.dirty}` at runtime. PR commit identity comes from the
head SHA; `${git.checkout_commit}` and `${git.short_checkout_commit}` expose the
actual checkout separately. Short hashes have 12 characters. No exact tag means
an empty string/list. Git lookup is lazy, cached per operation and local only;
tag and dirty checks run only when requested.

Find PTK by its custom wizard icon, with **PTk** on the hat. The project tree
uses theme colours to distinguish green jobs, purple workflows, orange variants,
gold configuration and blue repositories and commands. Colours follow your VS Code theme;
labels and icon shapes also identify each category.

- Expand **Jobs** and hover over a job to see **Run**, **Dry Run**,
  **Run Job or Workflow with Options** (gear) and **Show Help** (question mark). Each icon
  has a tooltip. Output appears in VS Code's task terminal; **Tasks: Terminate
  Task** stops a running task. Help displays the job's `--help` without running it
  or asking for parameters.
  **Dry Run** calls `ptk JOB --dry-run` or `ptk workflow run --dry-run NAME`: it shows what
  would run without executing the job steps or workflow jobs.
- Click **Open Latest Job or Workflow Report** (preview icon) on a job or
  workflow. Jobs open the report for the selected variant; workflows open the
  latest saved aggregate report. If no report is available, the task terminal
  prints an **Info** message that it has not run yet or its saved report was
  removed. The action does not run the job/workflow or prompt for parameters.
- Use **Run Job or Workflow with Options** (gear) on either kind of target.
  Jobs offer multiple variant checkboxes and `--from`/`--to` dropdowns showing
  the actual step names and titles. **More run options** provides feature and
  step-argument suggestions plus flags with help; `--env` requires **Dry run**.
  Workflows offer their help and one owner variant, with mappings resolved by PTK.
  Workspace workflows have no owner-variant selector. Saved tasks retain run
  options; choices are rechecked before starting the selected batch.
- Job parameters appear in the same form with text/number fields, boolean checkboxes, choices,
  help and authored defaults. Jobs with required non-secret parameters open it
  automatically. Enable **Override value** to supply a value; omitted parameters
  retain PTK's environment/default precedence. Template defaults are shown as
  expressions and resolved when PTK runs. Choose **Run job**, **Dry run** or
  **Cancel**. Lists use comma-separated values. Secret parameters stay in their
  declared credential environment and are excluded from the form.
- Expand a job to check one or more variants. Run starts them in parallel, each
  with a named task and dedicated terminal. Repository workflows select one owner
  variant. Selection is
  stored independently for that row in VS Code workspace state. Choose
  **Use project default** to clear it. PTK configuration files are unchanged.
- Use **Display Variant** to inspect resolved features. Edit variant definitions
  in the configuration tree and form, or in raw YAML.
- Expand **Workflows** to run or dry-run local workflows. Workflows retain their
  owner variant and its repository variant mappings. On CI, workflows can only be dry-run; individual
  jobs remain runnable. The help icon displays workflow usage.
- Expand **Built-in commands** to browse the CLI tree, including **self-service > creds**,
  configuration, variants and **help**. **CLI help** displays `ptk --help`;
  **help** runs PTK's HTML help command. Use the play icon to run a command, the
  gear to choose options/arguments, or the question mark for its usage. Required
  arguments are prompted automatically; optional values retain PTK defaults when
  omitted. Credential values and vault passwords are entered through PTK's hidden
  terminal prompts. Command names and credential names are ordinary arguments;
  never enter secret values into the extension's option prompts.
- Use **Open Latest Job or Workflow Report**, **Validate Configuration** and **Open
  Configuration File** from the command palette. Available operations follow
  PTK's maintainer permissions. Report files and explicit opening use the machine
  running PTK; no local browser-link server is started.

The built-in tree omits the duplicate `run` and `report` branches,
including their workflow equivalents. These operations are available directly
on jobs/workflows. Other built-in commands and CLI help remain available.

Multiple VS Code folders and VMR member repositories are supported. The extension
refreshes after PTK YAML and VMR project-list changes and after PTK tasks finish;
**Refresh Projects** forces another discovery. Configuration copies inside
virtual environments, installed packages and generated output are ignored, except
for files reported by PTK as configuration sources. Discovery requests are serialized
and repeated requests are coalesced. A broken VMR member is shown with its error while healthy
members remain usable.
The command tree comes from PTK's inventory, including its role restrictions.
Jobs with no required non-secret parameters and local workflows also appear in
**Tasks: Run Task**. Saved `project-toolkit` tasks retain their `variant`, `params`
and `preview` fields. Supply required parameters in `params`, or launch through
the Project Toolkit commands to get interactive prompts. Only non-secret string
values belong in task parameters.
Built-in tasks use `kind: "builtin"`, the full command path as `name` (for example
`"maintainer config show"`), and an `inputs` mapping of CLI parameter names to arrays of
literal strings (for example `{"path": ["project.name"], "fmt": ["json"]}`).
Saved tasks with `help: true` remain help requests on rerun. Built-in commands are
available from the sidebar/palette and are not automatically added to Run Task.

## Configuration tree and form

**Configuration** displays PTK's logical schema tree, independent of the files
that store it. Jobs, workflows, variants, Artifactory events and other sections
open at their schema path. The installed PTK supplies the authored values,
schema, source locations and loading/validation errors through
`describe --json --configuration`. The extension has no configuration discovery
or merge implementation and does not substitute a bundled schema for the runtime.
PTK and the extension must both support this configuration interface. Discovery
reports an error if the installed PTK does not provide it.

Text and number fields stay local while you type. Leaving a field, pressing
**Save** / **Ctrl/Cmd+S**, or navigating to another section applies the finished
edit; the project form then saves and reloads it through PTK. Checkboxes, choices
and structural actions apply immediately. Save replies preserve active text,
focus and the cursor; unchanged inventories do not redraw the tree. Add actions
are queued in order, and a watcher refresh cannot acknowledge an older snapshot
that hides the newly added item. The next field name survives save replies.

Use the VS Code tree for navigation. The form has no second navigation sidebar;
breadcrumbs show the current field path. List rows show step names or their values
instead of item numbers, and named steps open their fields directly.
Compact rows place labels, values and actions together; narrow editor columns
reflow vertically. Hover a field label or its **?** button for a short explanation,
or activate **?** with the mouse or keyboard to expand help, defaults and constraints.
Descriptions come from Pydantic field metadata in the installed PTK schema,
including context-specific meanings such as job restrictions versus skipped steps.
The optional-field selector previews this help before adding a field.
Both tree and form show scalar fields before objects and lists. Schema order
groups the root into identity, variants/components, jobs/workflows, execution
settings, tools/credentials, artifacts/versioning and output settings. Root scalar
metadata comes first. PTK carries explicit field-order metadata so sorted JSON
cannot turn this into alphabetical order. List items retain their authored order,
including executable steps; display ordering never rewrites YAML.
Edits go to the owning document supplied by PTK. Adding a job, workflow or variant
creates its conventional file. Components are registered in project settings;
their features and dependencies live in `component.variants.ptk.yml` beside their
code. Renaming an entity moves its file, and deleting it removes its file.
New items recursively include their required fields, minimum list/map entries
and creation hints supplied by PTK. Workflow invocations choose an existing local job when available. Enter a
qualified `REPO:JOB` target for cross-repository calls. Configure dependencies
with `needs`, referencing invocation IDs in the workflow’s `jobs` mapping. Empty text fields have a red border and a fill-in
message that clears as you type. Zero and false are treated as filled values.
Starter URLs use example.invalid; replace them with your own settings before use.
Source fingerprints reject stale edits, and unsaved YAML documents must be saved
or undone before using the project form.

**Raw YAML** opens a source chooser. The optional file editor retains normal
VS Code save/undo behavior and uses PTK's schema for that specific document.
Simple source edits preserve comments and scalar spelling. Use Raw YAML for
aliases or complex values that the form cannot safely edit.

Loading errors appear in the tree and Problems panel, with links to their source.
The **Validate Configuration** toolbar action is always available. A workspace
without `.main.ptk.yml` displays **No PTK project found** and offers **PTK init**,
which asks for the configuration directory.

Expand a job or repository workflow to see variant checkboxes, or use its existing
variant selector. Jobs accept multiple variants; workflows retain one owner variant.
**Use project default** clears explicit selections and follows the configured default.
Unchecking the last selected variant also restores this default. Abstract variants
cannot be selected. Selected names appear beside the parent row and are remembered
independently per target. Checkbox changes update that branch without reloading PTK
or the form.

Run, Dry Run, Clean and Re-run start a separate task for every selected job variant
in parallel. The parameter form opens once; explicit overrides apply to all selected
variants, while omitted values and template defaults resolve independently in PTK.
Canceling the form launches nothing. Open Report opens each selected variant's report.
Tasks have variant-qualified names and preserve their explicit variant when rerun.
The task picker lists each selected variant separately. A hand-written task without
an explicit variant uses the project default rather than the tree's multi-selection.
Repository workflows use PTK's existing repository variant mappings; workspace
workflows have no owner variant model. Use a repository-owned workflow for
variant-enabled jobs. There is no separate Variants group. Variant definitions remain editable under Configuration.

## Build and verify

With Node.js 22 or newer and npm installed, run from the PTK repository root:

```sh
ptk extension
# Or, with the checkout's uv environment:
uv run ptk extension
```

The job checks Node.js and npm, installs the locked build dependencies and runs
the package command. The VSIX is written to
`extensions/project-toolkit/project-toolkit-0.12.0.vsix`. Use `ptk extension --dry-run`
to preview the steps. Node.js must already be installed and available on PATH.

To run the same build directly from this extension folder:

```sh
npm ci --include=dev
npm run package
```

Packaging runs syntax checks and the Node test suite before producing the VSIX.
Set `PTK_TEST_PYTHON` to a Python interpreter with PTK's development dependencies
to include the real Node-to-CLI integration tests. For example, after `uv sync`
at the repository root, on Linux/macOS:

```sh
PTK_TEST_PYTHON="$PWD/../../.venv/bin/python" npm run package
```

CI uses `uv run ptk extension` to package the extension and run these integration
tests on Linux and Windows.
Controller tests inject the VS Code API and check task restoration, permissions,
workspace trust, multi-root selection and cancellation; they are not graphical
extension-host acceptance tests. For a manual smoke test, install the VSIX, open
`examples/quickstart`, dry-run and run a job, select a variant, and run the same
task again through **Tasks: Run Task**. Hover over the job icons to check their
tooltips, open job help and reports, and expand **Built-in commands > self-service > creds** to inspect
help and run `list`. Check **maintainer > config > show** with the gear to select a
configuration path and JSON output.
Before the first run, click a job/workflow's report icon and check the informational
terminal message; after a run, check that the matching report opens. Repeat with
a different job variant and with a workspace workflow.

The VSIX bundles its YAML document editor dependency; no npm installation is
needed by extension users. PTK owns configuration resolution, semantic validation,
role filtering and execution. Discovery does not run jobs or install tools, but
PTK may import configured project plugins, so workspace trust is required.

### Cleanup and workflow variants (0.3.0)

The selected variant also applies to repository-owned workflows; PTK resolves
other repositories using the owner's `repo_variants` mapping. Missing mappings
fail before execution or cleanup.

The trash and restart icons clean selected job/variant outputs or clean and
re-run them. Clean requires no job parameters. All four output categories are
removed; these actions execute immediately. Repository `clean-all` and workspace
`vmr-clean-all` are in Built-in commands and ask for confirmation in the terminal.
Use their Options action for `--dry-run` or `--yes`. Saved tasks accept `clean`
or `reRun`, with optional `preview: true` to inspect without deletion.

Update the CLI together with the extension. The config shorthand is now `-C`;
`-c` means clean. Binary folders now include the job name.

Browser regression tests exercise the actual form scripts, including slow typing,
focus/cursor preservation and navigation. Install Playwright with Chromium to run
them, or set `PTK_TEST_PLAYWRIGHT` to its module path and `PTK_TEST_CHROMIUM` to a
Chromium executable. Without Playwright these tests are explicitly skipped.
