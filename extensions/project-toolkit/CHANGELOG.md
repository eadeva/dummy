# Changelog

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
