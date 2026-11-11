# Changelog

## 0.0.0

- First release under the extension ID `bosch-xc-ce.project-toolkit` (previously `eadeva.project-toolkit`). `ptk self-service extension` installs the new ID and removes the old one; after a manual VSIX install, uninstall the old extension yourself.
- Add the Robert Bosch GmbH proprietary license (`LICENSE.txt`).
- Show a collapsed **VMR commands** branch first in a VMR folder, for the commands that act on every repository.
- Add **Open Advanced Help** (book icon) next to **CLI help** for the structured HTML help of a repository or the whole VMR; the plain `help` row is no longer listed separately.
- Show each step's own fields, including `outputs`, under its node in configuration graph trees.
- Place **CLI help** with its advanced help icon directly under each repository; **Configuration** lists GUI jobs under their own **GUIs** branch.
- Show the step's Python version in dependency graph labels.

## 0.26.1

- Add a dedicated parameter setup/edit form with readable type choices, descriptions, environment sources, required settings, typed defaults, variable templates and one-choice-per-line editing.
- Show CLI flag and step-reference examples. Review changes before saving; cancel preserves the original. Type/source changes explicitly reset incompatible draft values. Secrets cannot have saved defaults.
- Document shell option completion with ptk JOB -- followed by Tab and how to load shell registration.

## 0.26.0

- Workflow jobs are keyed directly by JOB or REPO:JOB, without a repeated job field. The wizard suggests unused jobs; needs and graph selection use the exact keys. Update PTk and the extension together and migrate existing workflows.
- Explicitly adding an optional Boolean field starts with the opposite of its schema default, including nested setup fields. Existing values and whole-object defaults are unchanged.
- Keep uses and the supported built-in operations.

## 0.25.4

- Give editor actions visible button borders and backgrounds, including navigation, Edit fields, Remove, help and expandable sections. Add consistent hover/pressed feedback and graph-node hover highlighting while retaining keyboard focus and theme colors.

## 0.25.3

- Repeated Rename clicks focus the existing name input and preserve its draft instead of adding duplicate controls.

## 0.25.2

- Add direct field editing and confirmed removal for selected graph steps. Remove or rename sibling prerequisite references in the same YAML edit, preserving comments. Do not replay rejected structural edits.
- Add searchable variable categories with counts, clearer insertion controls, keyboard navigation and theme-aware hover/selection contrast.

## 0.25.1

- Use the sidebar PTk wizard design for the extension details and listing icon.

## 0.25.0

- Replace job filters with portable `when` conditions, shared by runtime, job discovery and workflow matrix export. Remove all legacy filter fields.
- Explain required outputs and reject detached GUI output declarations. Missing outputs fail producers before releasing consumers.

## 0.24.2

- Remove step-level `only_variants` and `omit_variants` from configuration forms. Use `when` expressions for step conditions; job filters remain supported.

## 0.24.1

- Remove step-level `only_cx` from configuration forms; use `when: cx`. Keep job-level `only_cx`. Explain planning-time conditions in field help.

## 0.24.0

- Rename PTk runtime metadata to `cx`, matching `--cx`, `--no-cx`, `PTK_CX`, and the `cx` condition symbol. Legacy PTk CI aliases are removed; external provider environment names remain supported.
- Require inventory version 6; configuration interface version remains 5. Update PTk and the extension together.

## 0.23.2

- Use CX consistently in workflow availability labels and execution errors. Keep configuration keys and environment identifiers unchanged.

## 0.23.1

- Clarify external base ownership without filesystem write protection in schema field help.

## 0.23.0

- Describe external Git sources, pinned revisions and per-group file mappings in configuration forms. Distinguish unchanged external bases, project-owned overlays and separate generated outputs; remove the configs.sync job step.

## 0.22.0

- Guide creation of configuration fields, list items and named entities through Choose, Configure, Review and Create. Show required fields, descriptions, defaults, limits, optional-field help and variable insertion; retain a memory-only draft until creation and support cancellation.
- Offer CLI-owned command-line and Python mode choices, including editable local packages, for new steps and the first step of new jobs. Write ordinary configuration without a new runtime mode field. Update PTk to supply the new metadata; inventory/configuration interfaces remain version 5.
- Improve configuration graphs with command/type previews, dependent navigation, search, transitive relationship highlighting, direction selection, focus/fit/zoom and an expandable canvas. Retain view settings during the live form session and create nodes/dependents through the same setup flow.

## 0.21.1

- Support typed output declarations with optional artifact types. Keep variable completion on output paths and artifact types literal, matching completed-job output summaries and upload manifests.

## 0.21.0

- Add project-owned `outputs` and opt-in built-in `cache` configuration for steps and jobs, with no implicit build directory. Explain that outputs primarily describe workflow upload/download artifacts and cache correctness belongs to the project.
- Expose `--no-cache-ptk` for jobs, workflows and saved tasks. Roots execute; eligible dependents may reuse unchanged outputs. Reports distinguish reused work and its original run.

## 0.20.0

- Add a teal window-icon GUIs branch for `gui: true` jobs, retaining job actions, variants and saved tasks. PTk runs preparation normally and detaches the final launch command.
- Use blue jobs, purple workflows, orange variants/versions and neutral configuration/step icons. Give scalar fields a standard field icon and align form/graph colours.
- Require inventory version 5 with explicit GUI metadata and configuration interface version 5. Update PTk and the extension together.

## 0.19.0

- Match CLI entity colors: purple workflows, cyan jobs, blue steps, neutral gray built-in commands.
- Apply entity colors to navigation, configuration graph branches and graphical editor nodes. Other category and status colors retain their existing meaning.

## 0.18.0

- Match PTk's removal of third-party plugins and custom installer configuration.
- Offer only shipped operations, generators, report formats and credential providers.
- Preserve editable YAML and configuration diagnostics for obsolete plugin settings.

## 0.17.0

- Match PTk's component-qualified feature selections and per-step generators schema.
- Keep malformed generator configuration editable and recover after correction.
- Feature completion now uses `component.FEATURE`; variant outputs use `VARIANT_*`.

## 0.12.0

- Read PTk’s simplified report_formats and logging_history_backups fields and log-analysis rule schema.
- Update bundled schema and tree icons for the new reporting configuration.


## 0.11.0

- Use PTk discovery and its invocation directory/repository prefix; remove `--config` from tasks. Requires inventory protocol 3 and configuration interface 2.
- Add job/workflow run-options forms with variant choices, help and declared parameter values. Jobs support multiple variants and `--from`/`--to` step dropdowns with titles.
- Show PTk-provided feature and passthrough-step suggestions, preserve run options when restoring tasks, and reject stale choices before starting a batch.
- Install the bundled extension with the updated PTk package.

## 0.10.0

- Follow PTk's canonical job/workflow command paths, including maintainer-only targets, using inventory protocol 2.
- Use `ptk init`, `ptk validate`, `ptk self-service …` and `ptk maintainer …` throughout commands and task restoration.
- Use the same generic parameter interface for execution and `--dry-run`; workflow reports now use `report open --workflow`.
- Discover the reordered command groups from the installed PTk without exposing duplicate run commands in the sidebar.
- Update PTk and the bundled extension together; obsolete CLI aliases are removed.

## 0.9.0

- Select multiple job variants using tree checkboxes or the variant picker; run them in parallel with separate tasks and terminals. Repository workflows retain one owner variant.
- Apply parameter overrides once across the selected variants, preserve each variant on task reruns, and use the same selection for dry-run, cleanup and reports.
- Order scalar configuration fields before nested objects/lists in both tree and form, with a meaningful root order supplied by PTk's schema. Preserve authored list and step order.

## 0.8.0

- Use compact configuration rows with responsive layout and inline variable insertion.
- Add keyboard-accessible field help, defaults and constraints from the installed PTk schema. PTk's model now describes every configuration field.
- Add variant checkbox children under jobs and repository workflows. One selection is active per target; clearing it restores the project default.
- Update only the selected tree branch, retaining independent selections and avoiding configuration reloads.
- Preserve editing drafts, queued additions, required-field cues and help expansion during save acknowledgements.

## 0.7.0

- Add variable insertion and `${` autocomplete using the installed PTk's catalogue and template field capabilities.
- Filter variables by field context and current job, keep credentials restricted to step environment values and never preview environment or secret values.
- Preserve drafts, selection and focus during insertion, including outstanding structural save acknowledgements.
- PTk adds lazy, cached Git variables with PR head identity, separate checkout hashes, 12-character short hashes and exact-tag semantics. No network fetching; tag and dirty checks are independently lazy.

## 0.6.1

- Wait for superseding watcher refreshes before acknowledging configuration saves.
- Queue Add actions in order and preserve unfinished field names and clicks during save replies.
- Create required descendants, minimum collection entries and unique step names using the installed PTk schema.
- Select existing jobs for new workflow steps and show empty fields in red with a fill-in message.
- Restore theme-aware colors for project, job, workflow and configuration icons.

## 0.6.0

- Use PTk’s conventional document layout and section schemas through configuration interface v2.
- Create, rename and remove job, workflow and variant files in their known directories.
- Show component definitions beside their code, using explicitly registered component directories.
- Remove the per-change destination picker; PTk supplies file ownership.
- Preserve typing, drafts and focus while saving configuration.

## 0.5.1

- Apply text edits when leaving a field or saving; keep focus, drafts and cursor stable during save replies.
- Avoid tree redraws during source checks, unsaved YAML typing and unchanged refreshes.
- Use named steps and values for list rows, semantic icons and stable tree identities.
- Remove the form navigation sidebar; use the VS Code tree and breadcrumbs.

## 0.5.0

- Use the installed PTk's merged configuration tree, schema, sources and diagnostics.
- Fix Artifactory event initialization; named step defaults apply only to steps.
- Route edits to source files or move each change into a new fragment without duplicates.
- Show independent variant selectors on jobs and repository workflows.
- Keep validation available during loading errors and offer setup init without a project.
- Require PTk’s configuration interface for discovery and editing; remove older-CLI and include-format fallbacks.

## 0.4.0

- Browse configuration files as nested trees and edit their fields in a custom
  editor, with model-backed optional fields, job creation, list ordering and
  raw YAML switching. Preserve comments, anchors, includes, merge tags and
  VS Code's text document save/undo behavior.
- Replace job parameter prompts with a single form for required/optional values,
  types, choices, defaults, environment names and help. Preserve runtime default
  resolution and validate again when submitting a form after a refresh.
- Show the available PTk version consistently in HTML and Markdown reports.
- Keep configuration files reachable after a failed discovery, and bundle the
  editor dependencies into the VSIX.

## 0.3.3

- Use `uv run --no-sync` for discovery and every task entry point, including
  built-ins, help, reports and restored tasks. Launching PTk no longer updates
  its Python environment. Run `uv sync` explicitly when dependencies change.
- Ignore configuration copies in virtual environments, installed packages,
  generated output and bundled reference files. Explicitly included config
  files still refresh the tree.
- Serialize/coalesce discovery requests and refresh after PTk tasks finish.
  Click an unavailable workspace to see its exact discovery error in Output.
- Preserve variant-free help requests when rerunning tasks.

## 0.3.2

- Remove duplicate run, dry-run and report branches from the built-in command
  tree; use the actions on individual jobs and workflows instead.
- Add an inline Open Report action to jobs and workflows, including VMR
  workflows. Job reports follow the selected variant; workflows open their
  latest aggregate report. Report actions retain their meaning when rerun.
- Print an informational terminal message when a report is unavailable.
  Update PTk from the same checkout for `report open --if-exists` and
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
  to match PTk's CLI. Execution behavior and existing saved tasks are unchanged.

## 0.2.0

- Add inline job icons with tooltips for parameter entry and help, alongside run
  and preview. Help does not prompt for parameters or execute the job.
- Browse PTk's permitted built-in command tree, including setup, credentials and
  help; run commands with optional arguments directly from the sidebar.
- Keep credential values in PTk's hidden terminal prompts and preserve help and
  built-in arguments when restoring saved tasks.
- Support both repository and VMR commands, with CLI help available on older PTk
  versions and an update hint for the new command inventory.

## 0.1.0

- Add project, job, workflow, variant and configuration navigation.
- Run and preview through process tasks, with non-secret parameter prompts.
- Support multi-root workspaces, VMRs and per-project variant selection.
- Respect workspace trust, PTk roles and local-only workflow execution.
- Preserve preview mode and parameters when restoring configured tasks.
