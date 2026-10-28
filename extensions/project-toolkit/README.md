# Project Toolkit

Run PTK jobs, local workflows and built-in commands from VS Code, with a project
sidebar, help, variant selection, parameter forms, a configuration editor and reports.

## Install

1. Install PTK from the same checkout/version as this extension. The CLI must
   support `ptk describe --json` (inventory schema version 1).
2. In VS Code, run **Extensions: Install from VSIX...** and select
   `project-toolkit-0.4.0.vsix`. You can also use
   `code --install-extension project-toolkit-0.4.0.vsix`.
3. Open your PTK repository or VMR workspace, trust its contents, then open
   **Project Toolkit** in the activity bar.

VS Code 1.96 or newer is required. The extension runs on the workspace host;
for SSH, WSL or Dev Containers, install PTK on that host. The extension is
distributed as a VSIX, without a Marketplace publication.

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

## Use

Find PTK by its custom wizard icon, with **PTk** on the hat. The project tree
uses theme colours to distinguish green jobs, purple workflows, orange variants,
gold configuration files and blue repositories and commands. The selected variant
has a green checkmark and a **selected** label. Colours follow your VS Code theme;
labels and icon shapes also identify each category.

- Expand **Jobs** and hover over a job to see **Run**, **Dry Run**,
  **Run Job with Parameters** (gear) and **Show Help** (question mark). Each icon
  has a tooltip. Output appears in VS Code's task terminal; **Tasks: Terminate
  Task** stops a running task. Help displays the job's `--help` without running it
  or asking for parameters.
  **Dry Run** calls `ptk dry-run JOB` or `ptk workflow dry-run NAME`: it shows what
  would run without executing the job or workflow steps.
- Click **Open Latest Job or Workflow Report** (preview icon) on a job or
  workflow. Jobs open the report for the selected variant; workflows open the
  latest saved aggregate report. If no report is available, the task terminal
  prints an **Info** message that it has not run yet or its saved report was
  removed. The action does not run the job/workflow or prompt for parameters.
  Update PTK from the same checkout as extension 0.3.2 for this action.
- Use the parameter icon or **Run Job with Parameters** in the command palette
  to open a single form with text/number fields, boolean checkboxes, choices,
  help and authored defaults. Jobs with required non-secret parameters open it
  automatically. Enable **Override value** to supply a value; omitted parameters
  retain PTK's environment/default precedence. Template defaults are shown as
  expressions and resolved when PTK runs. Choose **Run job**, **Dry run** or
  **Cancel**. Lists use comma-separated values. Secret parameters stay in their
  declared credential environment and are excluded from the form.
- Click a **Variant**, or use **Select Variant for Jobs**. The selection is stored
  per repository in VS Code workspace state. Choose **Use project default** to
  clear it. PTK configuration files are unchanged by selection.
- Use **Display Variant** to inspect resolved features. Edit variant definitions
  in the configuration tree and form, or in raw YAML.
- Expand **Workflows** to run or dry-run local workflows. Workflows retain their
  owner variant and its repository variant mappings. On CI, workflows can only be dry-run; individual
  jobs remain runnable. The help icon displays workflow usage.
- Expand **Built-in commands** to browse the CLI tree, including **setup > creds**,
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

The built-in tree omits the duplicate `run`, `dry-run` and `report` branches,
including their workflow equivalents. These operations are available directly
on jobs/workflows. Other built-in commands and CLI help remain available.

Multiple VS Code folders and VMR member repositories are supported. The extension
refreshes after PTK YAML and VMR project-list changes and after PTK tasks finish;
**Refresh Projects** forces another discovery. Configuration copies inside
virtual environments, installed packages and generated output are ignored, except
for files explicitly included by a project. Discovery requests are serialized
and repeated requests are coalesced. A broken VMR member is shown with its error while healthy
members remain usable.
The command tree comes from PTK's inventory, including its role restrictions.
If **Update PTK to browse built-in commands** appears, update the CLI from this
checkout and refresh. Job actions and CLI help still work with older inventories.

Jobs with no required non-secret parameters and local workflows also appear in
**Tasks: Run Task**. Saved `project-toolkit` tasks retain their `variant`, `params`
and `preview` fields. Supply required parameters in `params`, or launch through
the Project Toolkit commands to get interactive prompts. Only non-secret string
values belong in task parameters.
Built-in tasks use `kind: "builtin"`, the full command path as `name` (for example
`"setup config show"`), and an `inputs` mapping of CLI parameter names to arrays of
literal strings (for example `{"path": ["project.name"], "fmt": ["json"]}`).
Saved tasks with `help: true` remain help requests on rerun. Built-in commands are
available from the sidebar/palette and are not automatically added to Run Task.

## Configuration tree and form

Expand **Configuration** and a source file to browse its sections, jobs, steps
and scalar fields. Click a file or field to open **PTK Configuration**. Add jobs,
rename dictionary entries, add optional model fields, change types for union
fields, and add/remove/reorder list items. The form edits the source file you
selected; includes are never flattened into the entry file.

Edits update VS Code's text document, with normal unsaved indicators, undo/redo
and save. Use **Save** or Ctrl/Cmd+S, or **Save & validate** to save and launch
PTK's project validation in the terminal. Semantic constraints, cross-file
references and plugin options remain PTK's responsibility. Fields may be
incomplete while editing. **Raw YAML** switches to the text editor;
**Open PTK Form** in its title bar switches back. It is also available in the
command palette and via **Reopen Editor With… > PTK Configuration**.

The form preserves comments, YAML anchors, include paths and merge tags; YAML
spacing may be normalized on edit. Aliases, includes and complex mapping keys
are shown as authored values and edited in raw YAML. Files with YAML syntax
errors still offer the raw editor. External changes refresh the form; stale
edits are rejected instead of overwriting newer content.

Optional fields come from the bundled PTK model schema. Update the CLI and
extension together when the model changes. **Schema for this file** selects a
fragment model for files included inside a specific field; variants and step
lists are recognized automatically. The configuration tree shows authored
values, while job execution uses PTK's fully resolved configuration.

## Build and verify

With Node.js 22 or newer and npm installed, run from the PTK repository root:

```sh
ptk extension
# Or, with the checkout's uv environment:
uv run ptk extension
```

The job checks Node.js and npm, installs the locked build dependencies and runs
the package command. The VSIX is written to
`extensions/project-toolkit/project-toolkit-0.4.0.vsix`. Use `ptk dry-run extension`
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
tooltips, open job help and reports, and expand **Built-in commands > setup > creds** to inspect
help and run `list`. Check **setup > config > show** with the gear to select a
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
