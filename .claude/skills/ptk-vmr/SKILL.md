---
name: ptk-vmr
description: Configure or troubleshoot a PTK virtual monorepo, shared workspace commands, credential conflicts, and per-job environment/tool isolation.
---

# PTK VMR workflows

1. Read [docs/cli.rst](../../../docs/cli.rst) and [docs/configuration.rst](../../../docs/configuration.rst). Run `ptk repos` and inspect each participating repository's root `.main.ptk.yml`. Confirm unique aliases and existing repository-relative `config_path` directories. From a repository, resolve its root `.git` symlink/junction or `gitdir:` file: only a target inside `.repo` establishes automatic membership. A parent `.repo` or ordinary Git worktree pointer is insufficient. At the workspace root, `.repo` directly activates VMR mode and `.repo/project.list` supplies members; if missing, report `repo sync` guidance, never scan recursively.
2. To initialize missing configs across a VMR, obtain the user's config-folder choice and preview `ptk setup init --config-dir PATH --dry-run`, then run `ptk setup init --config-dir PATH --yes`. The path is required and relative to each repository root; apply it to all new members. On a terminal, omission prompts once with no default. Omit DIRECTORY for all unconfigured checked-out members; supply DIRECTORY for just one project. Existing root entries are skipped, never rewritten, including invalid configs. Init uses the full member index, not `ptk repos` (which only lists configured members). Manual workspaces use explicit members or direct child Git repositories; do not scaffold build folders. Read the per-member results and count. Preserve the repository root as the execution directory.
3. Validate the workspace with `ptk setup config validate`; inspect a repository with `ptk ALIAS setup config show --sources`. Global options precede the alias.
4. Use workspace `setup creds list` to find shared names and `ALIAS/NAME` conflicts. Listing does not unlock stores. Use `setup creds set NAME` only when provisioning was requested. Credential tests run configured commands in each owning repository and can have external effects; inspect those commands first.
5. Install per repository/job: `ptk ALIAS setup install --job JOB --dry-run`, then the authorized installation. There is no workspace-wide installer. Preview execution with `ptk ALIAS dry-run JOB`.
6. Keep `environment.isolate: true` and `inherit_path: false`. Declare needed host variables with `keep`, configured variables with `set`, and credentials with step `secrets`. Prefer versioned managed tools. Do not fix missing tools by adding every cached installation to PATH. Use job-level `environment` only for deliberate overrides.
7. Read workspace `report list` / `report summary` and `variant list` / `variant check`. Keep variant edits, jobs and report exports repository-qualified.
8. Verify the affected commands from the workspace root and a nested git-repo member. Check a nearby standalone repository, repeated initialization with existing configs preserved, and conflicting credential definitions. Re-run `ptk repos` after changing the member index. Use disposable workspaces for tests that create or modify files.

For a manual VMR, create a workspace-root `.main.ptk.yml` containing `virtual_monorepo: true`, optionally `members: [nested/repo, other]`. It marks its containing directory, not its parent. Without `members`, inspect direct child directories only. Invoke grouped commands from that marked workspace; ordinary manual members remain standalone when invoked directly. A project's entry-level `virtual_monorepo: false` opts out of automatic membership and workspace listings. Omit it for automatic detection; do not add it to starter files by default. Discovery fields are literal entry metadata and cannot come from fragments or `--set`.

For version discovery, read [docs/versioning.rst](../../../docs/versioning.rst). Keep `.main.ptk.yml` minimal; use `ptk setup init --config-dir PATH` for starter fragments. Maintain `versioning.ptk.yml`, never commit `.gen.version.ptk.yml`. Use `PTK_VERSION_ALIAS_COMPONENT_NAME` and `${version.projects.alias.value}`; generators consume the run snapshot. Declare VMR version dependencies and their variants explicitly. Do not add bump/tag operations.


To combine existing jobs locally, use [workflow configuration](../../../docs/workflows.rst) and the `ptk-workflow-authoring` skill. Put `workflow.ptk.yml` in the configured folder; workspace-owned workflows belong at the VMR root. Workflows preserve each call's repository settings and never run wholesale on CX. GitHub job/template generation is deferred.

Maintainer lists are independent: each repository's configured folder contains
its own `maintainers.ptk.yml`; the VMR root may have a separate list for workspace
editor setup and restricted workspace workflows. Lists contain login strings.
Root membership does not grant member permissions. Combined editor setup checks
all target permissions before writing; use a repository-qualified command for a
single permitted target. See [configuration](../../../docs/configuration.rst).
