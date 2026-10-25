---
name: ptk-vmr
description: Configure or troubleshoot a PTK virtual monorepo, shared workspace commands, credential conflicts, and per-action environment/tool isolation.
---

# PTK VMR workflows

1. Read `docs/cli.rst` and `docs/configuration.rst`. Run `ptk repos` and inspect each participating repository's root `.main.ptk.yml`. Confirm unique aliases and existing repository-relative `config_path` directories. From a repository, resolve its root `.git` symlink/junction or `gitdir:` file: only a target inside `.repo` establishes automatic membership. A parent `.repo` or ordinary Git worktree pointer is insufficient. At the workspace root, `.repo` directly activates VMR mode and `.repo/project.list` supplies members; if missing, report `repo sync` guidance, never scan recursively.
2. Use the tested starter at `examples/authoring/.main.ptk.yml` and its configuration fragments when creating a repository. Preserve the repository root as the execution directory.
3. Validate the workspace with `ptk setup config validate`; inspect a repository with `ptk ALIAS setup config show --sources`. Global options precede the alias.
4. Use workspace `setup creds list` to find shared names and `ALIAS/NAME` conflicts. Listing does not unlock stores. Use `setup creds set NAME` only when provisioning was requested. Credential tests run configured commands in each owning repository and can have external effects; inspect those commands first.
5. Install per repository/action: `ptk ALIAS setup install --action ACTION --dry-run`, then the authorized installation. There is no workspace-wide installer. Preview execution with `ptk ALIAS dry-run ACTION`.
6. Keep `environment.isolate: true` and `inherit_path: false`. Declare needed host variables with `keep`, configured variables with `set`, and credentials with step `secrets`. Prefer versioned managed tools. Do not fix missing tools by adding every cached installation to PATH. Use action-level `environment` only for deliberate overrides.
7. Read workspace `report list` / `report summary` and `variant list` / `variant check`. Keep variant edits, actions and report exports repository-qualified.
8. Validate regressions with `tests/test_workspace.py`, `tests/test_workspace_discovery.py`, `tests/test_review_regressions.py` and the two-version tool test in `tests/test_tools.py`. Include invocation from a nested git-repo member, a nearby standalone repository, cache refresh on a second invocation, and a conflicting credential definition. Reuse one `WorkspaceDiscovery` across routed apps, credentials and version dependencies; do not add a process-global cache or load unselected includes during discovery.

For a manual VMR, create a workspace-root `.main.ptk.yml` containing `virtual_monorepo: true`, optionally `members: [nested/repo, other]`. It marks its containing directory, not its parent. Without `members`, inspect direct child directories only. Invoke grouped commands from that marked workspace; ordinary manual members remain standalone when invoked directly. A project's entry-level `virtual_monorepo: false` opts out of automatic membership and workspace listings. Omit it for automatic detection; do not add it to starter files by default. Discovery fields are literal entry metadata and cannot come from includes, overlays or `--set`.

For version discovery, read `docs/versioning.rst` and exercise `tests/test_versioning.py`. Keep `.main.ptk.yml` minimal; use `ptk setup init --config-dir PATH` for starter fragments. Maintain `versioning.ptk.yml`, never commit `.gen.version.ptk.yml`. Use `PTK_VERSION_ALIAS_COMPONENT_NAME` and `${version.projects.alias.value}`; generators consume the run snapshot. Declare VMR version dependencies and their variants explicitly. Do not add bump/tag operations.
