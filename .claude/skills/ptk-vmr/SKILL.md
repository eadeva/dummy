---
name: ptk-vmr
description: Configure or troubleshoot a PTK virtual monorepo, shared workspace commands, credential conflicts, and per-job environment/tool isolation.
---

# PTK VMR workflows

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [docs/reference/cli.rst](../../../docs/reference/cli.rst) and [docs/guides/configuration.rst](../../../docs/guides/configuration.rst). Run `ptk repos` and inspect each participating repository's root `.main.ptk.yml`. Confirm unique aliases and existing repository-relative `config_path` directories. From a repository, resolve its root `.git` symlink/junction or `gitdir:` file: only a target inside `.repo` establishes automatic membership. A parent `.repo` or ordinary Git worktree pointer is insufficient. At the workspace root, `.repo` directly activates VMR mode and `.repo/project.list` supplies members; if missing, report `repo sync` guidance, never scan recursively.
2. To initialize missing configs across a VMR, reuse the requested or established config-folder choice, asking only when missing. Preview `ptk init --config-dir PATH --dry-run`, then run `ptk init --config-dir PATH --yes`. The path is required and relative to each repository root; apply it to all new members. On a terminal, omission prompts once with no default. Omit DIRECTORY for all unconfigured checked-out members; supply DIRECTORY for just one project. Existing root entries are skipped, never rewritten, including invalid configs. Init uses the full member index, not `ptk repos` (which only lists configured members). Manual workspaces use explicit members or direct child Git repositories; do not scaffold build folders. Read the per-member results and count. Preserve the repository root as the execution directory.
3. Validate the workspace with `ptk validate`; inspect a repository with `ptk ALIAS maintainer config show --sources`. Global options precede the alias.
4. Use workspace `self-service creds list` to find shared names and `ALIAS/NAME` conflicts. Listing does not unlock stores. Use `self-service creds set NAME` only when provisioning was requested. Credential tests run configured commands in each owning repository and can have external effects; inspect those commands first.
5. Install per repository/job: `ptk ALIAS self-service tools --job JOB --dry-run`, then the authorized installation. There is no workspace-wide installer. Preview execution with `ptk ALIAS JOB --dry-run`.
6. Keep `environment.isolate: true` and `inherit_path: false`. Declare needed host variables with `keep`, configured variables with `set`, and credentials with step `secrets`. Prefer versioned managed tools. Do not fix missing tools by adding every cached installation to PATH. Use job-level `environment` only for deliberate overrides.
7. Inspect permitted commands with `ptk --help` and `ptk describe --json`; use `variant list` and `validate --variants` where available. Open a workflow report with `ptk report open --workflow NAME`; export job reports through the owning repository. Do not invent report-list or report-summary commands.
8. Verify the affected commands from the workspace root and a nested git-repo member. Check a nearby standalone repository, repeated initialization with existing configs preserved, and conflicting credential definitions. Re-run `ptk repos` after changing the member index. Use disposable workspaces for tests that create or modify files.

For a manual VMR, create a workspace-root `.main.ptk.yml` containing `virtual_monorepo: true`, optionally `members: [nested/repo, other]`. It marks its containing directory, not its parent. Without `members`, inspect direct child directories only. Invoke grouped commands from that marked workspace; ordinary manual members remain standalone when invoked directly. A project's entry-level `virtual_monorepo: false` opts out of automatic membership and workspace listings. Omit it for automatic detection; do not add it to starter files by default. Discovery fields are literal entry metadata and cannot come from section files or `--set`.

Use [versioning](../ptk-versioning/SKILL.md) for cross-repository version dependencies and [workflow authoring](../ptk-workflow-authoring/SKILL.md) for orchestration. Keep each call's configuration and identity in its owning repository.

Maintainer lists are independent: each repository's configured folder contains
its own `maintainers.ptk.yml`; the VMR root may have a separate list for workspace
editor setup and restricted workspace workflows. Lists contain login strings.
Root membership does not grant member permissions. Workspace synchronization checks
all target permissions before writing; use a repository-qualified command for a
single permitted target. See [configuration](../../../docs/guides/configuration.rst).
