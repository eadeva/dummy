# Project Toolkit

Run PTK jobs, local workflows and built-in commands from VS Code, with a project
sidebar, help, variant selection, parameter prompts, configuration and reports.

## Install

1. Install PTK from the same checkout/version as this extension. The CLI must
   support `ptk describe --json` (inventory schema version 1).
2. In VS Code, run **Extensions: Install from VSIX...** and select
   `project-toolkit-0.2.1.vsix`. You can also use
   `code --install-extension project-toolkit-0.2.1.vsix`.
3. Open your PTK repository or VMR workspace, trust its contents, then open
   **Project Toolkit** in the activity bar.

VS Code 1.96 or newer is required. The extension runs on the workspace host;
for SSH, WSL or Dev Containers, install PTK on that host. The extension is
distributed as a VSIX, without a Marketplace publication.

If PTK is not on the extension host's PATH, set **Project Toolkit: Executable**
to its absolute path. To use a uv-managed project, configure:

```json
{
  "projectToolkit.executable": "uv",
  "projectToolkit.arguments": ["run", "ptk"]
}
```

The executable setting is a program name or path, with each argument entered
separately. With a VMR, use an installed PTK executable if its root has no uv
project. Discovery errors appear in **Output > Project Toolkit** and on the
workspace node. Set `projectToolkit.discoveryTimeout` (seconds) for slow projects.

## Use

- Expand **Jobs** and hover over a job to see four icons: **Run**, **Dry Run**,
  **Run Job with Parameters** (gear) and **Show Help** (question mark). Each icon
  has a tooltip. Output appears in VS Code's task terminal; **Tasks: Terminate
  Task** stops a running task. Help displays the job's `--help` without running it
  or asking for parameters.
  **Dry Run** calls `ptk dry-run JOB` or `ptk workflow dry-run NAME`: it shows what
  would run without executing the job or workflow steps.
- Use the parameter icon or **Run Job with Parameters** in the command palette
  to override optional parameters. Required non-secret parameters are prompted
  automatically. Lists use comma-separated values; PTK validates the supplied
  types. Configure secret parameters through their declared environment variables.
- Click a **Variant**, or use **Select Variant for Jobs**. The selection is stored
  per repository in VS Code workspace state. Choose **Use project default** to
  clear it. PTK configuration files are unchanged by selection.
- Use **Display Variant** to inspect resolved features. Variant creation and
  editing are performed in the project's YAML configuration.
- Expand **Workflows** to run or dry-run local workflows. Workflows retain their
  configured per-job variants. On CI, workflows can only be dry-run; individual
  jobs remain runnable. The help icon displays workflow usage.
- Expand **Built-in commands** to browse the CLI tree, including **setup > creds**,
  configuration, variants, reports and **help**. **CLI help** displays `ptk --help`;
  **help** runs PTK's HTML help command. Use the play icon to run a command, the
  gear to choose options/arguments, or the question mark for its usage. Required
  arguments are prompted automatically; optional values retain PTK defaults when
  omitted. Credential values and vault passwords are entered through PTK's hidden
  terminal prompts. Command names and credential names are ordinary arguments;
  never enter secret values into the extension's option prompts.
- Use **Open Latest Job Report**, **Validate Configuration** and **Open
  Configuration File** from the command palette. Available operations follow
  PTK's maintainer permissions. Reports use PTK's terminal/browser links; remote
  sessions may require port forwarding.

Multiple VS Code folders and VMR member repositories are supported. The extension
refreshes after PTK YAML and VMR project-list changes; **Refresh Projects** forces
another discovery. A broken VMR member is shown with its error while healthy
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

## Build and verify

With Node.js 22 or newer and npm installed, run from the PTK repository root:

```sh
ptk extension
# Or, with the checkout's uv environment:
uv run ptk extension
```

The job checks Node.js and npm, installs the locked build dependencies and runs
the package command. The VSIX is written to
`extensions/project-toolkit/project-toolkit-0.2.1.vsix`. Use `ptk dry-run extension`
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
task again through **Tasks: Run Task**. Hover over the four job icons to check their
tooltips, open job help, and expand **Built-in commands > setup > creds** to inspect
help and run `list`. Check **setup > config > show** with the gear to select a
configuration path and JSON output.

The extension has no runtime npm dependencies. PTK owns configuration parsing,
role filtering and execution. Discovery does not run jobs or install tools, but
PTK may import configured project plugins, so workspace trust is required.
