# Changelog

## 0.11.0

- Use PTK discovery and its invocation directory/repository prefix; remove `--config` from tasks. Requires inventory protocol 3 and configuration interface 2.
- Add job/workflow run-options forms with variant choices, help and declared parameter values. Jobs support multiple variants and `--from`/`--to` step dropdowns with titles.
- Show PTK-provided feature and passthrough-step suggestions, preserve run options when restoring tasks, and reject stale choices before starting a batch.
- Install the bundled extension with the updated PTK package.

## 0.10.0

- Follow PTK's canonical job/workflow command paths, including maintainer-only targets, using inventory protocol 2.
- Use `ptk init`, `ptk validate`, `ptk self-service …` and `ptk maintainer …` throughout commands and task restoration.
- Use the same generic parameter interface for execution and `--dry-run`; workflow reports now use `report open --workflow`.
- Discover the reordered command groups from the installed PTK without exposing duplicate run commands in the sidebar.
- Update PTK and the bundled extension together; obsolete CLI aliases are removed.

## 0.9.0

- Select multiple job variants using tree checkboxes or the variant picker; run them in parallel with separate tasks and terminals. Repository workflows retain one owner variant.
- Apply parameter overrides once across the selected variants, preserve each variant on task reruns, and use the same selection for dry-run, cleanup and reports.
- Order scalar configuration fields before nested objects/lists in both tree and form, with a meaningful root order supplied by PTK's schema. Preserve authored list and step order.

## 0.8.0

- Use compact configuration rows with responsive layout and inline variable insertion.
- Add keyboard-accessible field help, defaults and constraints from the installed PTK schema. PTK's model now describes every configuration field.
- Add variant checkbox children under jobs and repository workflows. One selection is active per target; clearing it restores the project default.
- Update only the selected tree branch, retaining independent selections and avoiding configuration reloads.
- Preserve editing drafts, queued additions, required-field cues and help expansion during save acknowledgements.

## 0.7.0

- Add variable insertion and `${` autocomplete using the installed PTK's catalogue and template field capabilities.
- Filter variables by field context and current job, keep credentials restricted to step environment values and never preview environment or secret values.
- Preserve drafts, selection and focus during insertion, including outstanding structural save acknowledgements.
- PTK adds lazy, cached Git variables with PR head identity, separate checkout hashes, 12-character short hashes and exact-tag semantics. No network fetching; tag and dirty checks are independently lazy.

## 0.6.1

- Wait for superseding watcher refreshes before acknowledging configuration saves.
- Queue Add actions in order and preserve unfinished field names and clicks during save replies.
- Create required descendants, minimum collection entries and unique step names using the installed PTK schema.
- Select existing jobs for new workflow steps and show empty fields in red with a fill-in message.
- Restore theme-aware colors for project, job, workflow and configuration icons.

## 0.6.0

- Use PTK’s conventional document layout and section schemas through configuration interface v2.
- Create, rename and remove job, workflow and variant files in their known directories.
- Show component definitions beside their code, using explicitly registered component directories.
- Remove the per-change destination picker; PTK supplies file ownership.
- Preserve typing, drafts and focus while saving configuration.

## 0.5.1

- Apply text edits when leaving a field or saving; keep focus, drafts and cursor stable during save replies.
- Avoid tree redraws during source checks, unsaved YAML typing and unchanged refreshes.
- Use named steps and values for list rows, semantic icons and stable tree identities.
- Remove the form navigation sidebar; use the VS Code tree and breadcrumbs.

## 0.5.0

- Use the installed PTK's merged configuration tree, schema, sources and diagnostics.
- Fix Artifactory event initialization; named step defaults apply only to steps.
- Route edits to source files or move each change into a new fragment without duplicates.
- Show independent variant selectors on jobs and repository workflows.
- Keep validation available during loading errors and offer setup init without a project.
- Require PTK’s configuration interface for discovery and editing; remove older-CLI and include-format fallbacks.

## 0.4.0

- Browse configuration files as nested trees and edit their fields in a custom
  editor, with model-backed optional fields, job creation, list ordering and
  raw YAML switching. Preserve comments, anchors, includes, merge tags and
  VS Code's text document save/undo behavior.
- Replace job parameter prompts with a single form for required/optional values,
  types, choices, defaults, environment names and help. Preserve runtime default
  resolution and validate again when submitting a form after a refresh.
- Show the available PTK version consistently in HTML and Markdown reports.
- Keep configuration files reachable after a failed discovery, and bundle the
  editor dependencies into the VSIX.

## 0.3.3

- Use `uv run --no-sync` for discovery and every task entry point, including
  built-ins, help, reports and restored tasks. Launching PTK no longer updates
  its Python environment. Run `uv sync` explicitly when dependencies change.
- Ignore configuration copies in virtual environments, installed packages,
  generated output and bundled reference files. Explicitly included config
  files still refresh the tree.
- Serialize/coalesce discovery requests and refresh after PTK tasks finish.
  Click an unavailable workspace to see its exact discovery error in Output.
- Preserve variant-free help requests when rerunning tasks.

## 0.3.2

- Remove duplicate run, dry-run and report branches from the built-in command
  tree; use the actions on individual jobs and workflows instead.
- Add an inline Open Report action to jobs and workflows, including VMR
  workflows. Job reports follow the selected variant; workflows open their
  latest aggregate report. Report actions retain their meaning when rerun.
- Print an informational terminal message when a report is unavailable.
  Update PTK from the same checkout for `report open --if-exists` and
  `workflow report --if-exists` support.

## 0.3.1

- Replace the Activity Bar toolbox with the custom wizard and PTk lettering
  on its hat. The SVG follows the active theme's Activity Bar colour.
- Colour tree icons by category using the active VS Code theme: green jobs,
  purple workflows, amber variants, gold configuration and blue repositories
  and commands. Add category icons to the group headings.
- Mark the selected variant with a green checkmark as well as its text label.

## 0.2.1

- Rename Preview to Dry Run in command titles, tooltips, task labels and messages
  to match PTK's CLI. Execution behavior and existing saved tasks are unchanged.

## 0.2.0

- Add inline job icons with tooltips for parameter entry and help, alongside run
  and preview. Help does not prompt for parameters or execute the job.
- Browse PTK's permitted built-in command tree, including setup, credentials and
  help; run commands with optional arguments directly from the sidebar.
- Keep credential values in PTK's hidden terminal prompts and preserve help and
  built-in arguments when restoring saved tasks.
- Support both repository and VMR commands, with CLI help available on older PTK
  versions and an update hint for the new command inventory.

## 0.1.0

- Add project, job, workflow, variant and configuration navigation.
- Run and preview through process tasks, with non-secret parameter prompts.
- Support multi-root workspaces, VMRs and per-project variant selection.
- Respect workspace trust, PTK roles and local-only workflow execution.
- Preserve preview mode and parameters when restoring configured tasks.
