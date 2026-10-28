# Changelog

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
