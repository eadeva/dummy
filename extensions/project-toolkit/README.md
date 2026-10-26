# Project Toolkit

Run PTK jobs and local workflows from VS Code, with a project sidebar, variant
selection, previews, parameter prompts, configuration files and job reports.

## Install

1. Install PTK from the same checkout/version as this extension. The CLI must
   support `ptk describe --json` (inventory schema version 1).
2. In VS Code, run **Extensions: Install from VSIX...** and select
   `project-toolkit-0.1.0.vsix`. You can also use
   `code --install-extension project-toolkit-0.1.0.vsix`.
3. Open your PTK repository or VMR workspace, trust its contents, then open
   **Project Toolkit** in the activity bar.

VS Code 1.96 or newer is required. The extension runs on the workspace host;
for SSH, WSL or Dev Containers, install PTK on that host. This first version is
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

- Expand **Jobs** and use **Run** or **Preview**. Output appears in VS Code's task
  terminal; **Tasks: Terminate Task** stops a running task.
- Use **Run Job with Parameters** from a job's context menu or the command palette
  to override optional parameters. Required non-secret parameters are prompted
  automatically. Lists use comma-separated values; PTK validates the supplied
  types. Configure secret parameters through their declared environment variables.
- Click a **Variant**, or use **Select Variant for Jobs**. The selection is stored
  per repository in VS Code workspace state. Choose **Use project default** to
  clear it. PTK configuration files are unchanged by selection.
- Use **Display Variant** to inspect resolved features. Variant creation and
  editing are performed in the project's YAML configuration.
- Expand **Workflows** to run or preview local workflows. Workflows retain their
  configured per-job variants. On CI, workflows can only be previewed; individual
  jobs remain runnable.
- Use **Open Latest Job Report**, **Validate Configuration** and **Open
  Configuration File** from the command palette. Available operations follow
  PTK's maintainer permissions. Reports use PTK's terminal/browser links; remote
  sessions may require port forwarding.

Multiple VS Code folders and VMR member repositories are supported. The extension
refreshes after PTK YAML and VMR project-list changes; **Refresh Projects** forces
another discovery. A broken VMR member is shown with its error while healthy
members remain usable.

Jobs with no required non-secret parameters and local workflows also appear in
**Tasks: Run Task**. Saved `project-toolkit` tasks retain their `variant`, `params`
and `preview` fields. Supply required parameters in `params`, or launch through
the Project Toolkit commands to get interactive prompts. Only non-secret string
values belong in task parameters.

## Build and verify

From this folder, with Node.js 22 or newer:

```sh
npm ci
npm run package
```

Packaging runs syntax checks and the Node test suite before producing the VSIX.
Set `PTK_TEST_PYTHON` to a Python interpreter with PTK's development dependencies
to include the real Node-to-CLI integration tests. For example, after `uv sync`
at the repository root, on Linux/macOS:

```sh
PTK_TEST_PYTHON="$PWD/../../.venv/bin/python" npm run package
```

CI packages the extension and runs these integration tests on Linux and Windows.
Controller tests inject the VS Code API and check task restoration, permissions,
workspace trust, multi-root selection and cancellation; they are not graphical
extension-host acceptance tests. For a manual smoke test, install the VSIX, open
`examples/quickstart`, preview and run a job, select a variant, and run the same
task again through **Tasks: Run Task**.

The extension has no runtime npm dependencies. PTK owns configuration parsing,
role filtering and execution. Discovery does not run jobs or install tools, but
PTK may import configured project plugins, so workspace trust is required.
