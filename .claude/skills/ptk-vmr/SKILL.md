---
name: ptk-vmr
description: Configure or troubleshoot a PTK virtual monorepo, shared workspace commands, credential conflicts, and per-action environment/tool isolation.
---

# PTK VMR workflows

1. Read `docs/cli.rst` and `docs/configuration.rst`. Run `ptk repos` and inspect the root `.main.ptk.yml` of each participating repository. Confirm unique aliases and existing repository-relative `config_path` directories. Do not guess membership from a plain Git worktree pointer.
2. Use the tested starter at `examples/authoring/.main.ptk.yml` and its configuration fragments when creating a repository. Preserve the repository root as the execution directory.
3. Validate the workspace with `ptk setup config validate`; inspect a repository with `ptk ALIAS setup config show --sources`. Global options precede the alias.
4. Use workspace `setup creds list` to find shared names and `ALIAS/NAME` conflicts. Listing does not unlock stores. Use `setup creds set NAME` only when provisioning was requested. Credential tests run configured commands in each owning repository and can have external effects; inspect those commands first.
5. Install per repository/action: `ptk ALIAS setup install --action ACTION --dry-run`, then the authorized installation. There is no workspace-wide installer. Preview execution with `ptk ALIAS dry-run ACTION`.
6. Keep `environment.isolate: true` and `inherit_path: false`. Declare needed host variables with `keep`, configured variables with `set`, and credentials with step `secrets`. Prefer versioned managed tools. Do not fix missing tools by adding every cached installation to PATH. Use action-level `environment` only for deliberate overrides.
7. Read workspace `report list` / `report summary` and `variant list` / `variant check`. Keep variant edits, actions and report exports repository-qualified.
8. Validate regressions with `tests/test_workspace.py`, `tests/test_review_regressions.py` and the two-version tool test in `tests/test_tools.py`. Include invocation from a member subdirectory and a conflicting credential definition.
