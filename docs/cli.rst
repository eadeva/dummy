CLI command groups
==================

Use ``ptk setup`` to display the setup overview. Viewing this overview does not
install tools or change configuration. Project jobs remain top-level commands.
Help and completion show only commands available to the current user. The table
below includes maintainer commands for reference; see :doc:`configuration` for
the login-ID list and default restrictions.

Help shows separate boxes for Options, Jobs, Workflows and Commands, in that
order, omitting empty groups. At a VMR root, Repositories replaces Jobs.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Purpose
   * - ``ptk setup init [DIRECTORY]``
     - Initialize missing VMR configs, or create one project at DIRECTORY
   * - ``ptk setup completion powershell|bash|zsh|fish``
     - Generate shell Tab completion, even outside a PTK project
   * - ``ptk setup config show|validate|schema``
     - Inspect, validate and export project configuration
   * - ``ptk setup configs sync|check``
     - Generate and verify shared tool configurations
   * - ``ptk pre-commit run|check|install|uninstall|status|validate``
     - Run repository checks and manage local Git hooks
   * - ``ptk setup install``
     - Check tools and install missing or outdated versions
   * - ``ptk setup creds setup|set|list|test|remove``
     - Configure and manage credential providers
   * - ``ptk setup self``
     - Set up project configs and hooks; optionally tools
   * - ``ptk setup doctor``
     - Diagnose the local installation and project
   * - ``ptk setup vscode tasks``
     - Generate editor tasks
   * - ``ptk setup vscode`` / ``ptk setup vscode skills [--check]``
     - Set up tasks and offline skills/docs, or manage the skills alone
   * - ``ptk variant list|show|explain|check``
     - Inspect the product line
   * - ``ptk report open|export``
     - View and regenerate reports
   * - ``ptk workflow list|show|dry-run|run|report``
     - Inspect or execute local workflows, or open their latest report (execution is disabled on CX)
   * - ``ptk artifacts destination --job JOB``
     - Resolve Artifactory URL/repository/path for an external uploader; see :doc:`artifacts`
   * - ``ptk JOB`` / ``ptk run JOB``
     - Execute project jobs
   * - ``ptk dry-run JOB``
     - Preview execution

Put global options before the group, and installation options after ``install``::

   uv run ptk -C examples/quickstart/.main.ptk.yml setup config validate
   uv run ptk -C examples/quickstart/.main.ptk.yml setup install --job build --dry-run
   uv run ptk -C examples/quickstart/.main.ptk.yml setup creds list

The ``ptk init`` alias also remains available.

The former top-level ``config``, ``configs``, ``creds``, ``self-setup``, ``doctor``
and ``vscode`` commands remain callable aliases, hidden from help and completion.
Legacy ``ptk setup --job JOB --dry-run`` also remains supported. Bare
``ptk setup`` now shows help; use ``ptk setup install`` to install all configured
tools. Do not combine legacy installation options with a setup subcommand.

Terminal Tab completion
-----------------------

Completion works with the installed ``ptk`` executable, independently of any
editor. Enable it once in your current shell. In PowerShell::

   ptk setup completion powershell --double-tab | Out-String | Invoke-Expression

Add that same line to your ``$PROFILE`` to enable it in future terminals.
``--double-tab`` uses PSReadLine's ``Complete`` binding: Tab completes the unique
prefix; another Tab lists the remaining matches. This changes Tab for **all
commands** in that shell. Omit the flag to keep your current key bindings
(Windows PowerShell normally cycles matches with Tab). PSReadLine must be
available for the double-Tab binding; the PTK completer itself does not require it.
The registration script does not edit your profile automatically.

For Bash (4.4 or later), enable completion with::

   eval "$(ptk setup completion bash)"

Put that line in ``~/.bashrc`` for future terminals. Bash normally lists multiple
matches on the second Tab. For Zsh, after your usual ``compinit`` initialization::

   eval "$(ptk setup completion zsh)"

For Fish::

   ptk setup completion fish | source

You can save a generated script with ``--output PATH`` and source that file from
your shell profile instead. Its directory must already exist. Zsh and Fish use
their configured completion key bindings and display styles.

Examples (``<Tab>`` means press the key)::

   ptk <Tab><Tab>                   # available commands, jobs and workflows
   ptk build --<Tab><Tab>           # options for the configured build job
   ptk build --build-type <Tab>     # declared choice values
   ptk --variant <Tab><Tab>         # concrete variants and aliases
   ptk build --from <Tab><Tab>      # top-level step names
   ptk workflow run <Tab><Tab>      # available workflow names

Job names also complete after ``run``, report commands and ``--job`` options.
VMR completion includes repository aliases and repository-qualified workflows.
Suggestions respect command visibility and the current project configuration;
hidden aliases and maintainer-only commands remain hidden from ordinary users.
Type ``-`` to request option names. Choice and path parameters use native shell
completion; free-text and secret values are not guessed.

Each completion request starts a short-lived PTK process and reads the required
configuration. It does not execute jobs, initialize plugins, resolve Git/version
variables, read credential values or install tools. Configuration is read again
on the next request, so edits appear without a separate refresh. With missing or
invalid project configuration, built-in commands still complete.

Global options and variant inspection
-------------------------------------

``-V NAME`` / ``--variant NAME`` is a global option, placed before the command
and, in a VMR, before the repository alias::

   ptk -V debug build
   ptk -V debug run build
   ptk -V debug dry-run build
   ptk -V debug firmware build
   ptk -V debug variant show
   ptk -V debug report open build

It selects the variant for jobs, version discovery/generation, report commands,
artifact destinations and ``variant show`` when NAME is omitted. An explicit
NAME on ``variant show`` takes precedence. It is irrelevant to setup/config/help/pre-commit,
variant list/check/explain (which have their own explicit selection), describe,
and workflow list/show. Workflow execution selects the owner variant and resolves
other repositories through its ``repo_variants`` mappings.
The option is no longer accepted after a job or subcommand.

``--ci`` / ``--no-ci`` is maintainer-only: hidden from user help and completion,
and rejected on direct invocation. With neither flag, CI detection works for all
users. In a VMR, a repository-qualified command checks that member's maintainer
list; workspace commands check the root list. Member operations also enforce
their own permissions. The default mode remains automatically detected.

``variant list``, ``show``, ``explain`` and ``check`` are read-only. Edit the YAML
configuration directly to change the product line or configured default.
Persistent variant editing commands and the desktop editor have been removed.

Pre-commit commands
-------------------

The built-in ``pre-commit`` group uses the current repository's configured
pre-commit file and PTK's managed runtime. No separate pre-commit executable on
PATH is required. In a VMR, select a member: ``ptk ALIAS pre-commit ...``.
There is no implicit operation across all repositories.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Behavior
   * - ``ptk pre-commit run [HOOK]``
     - Run checks on staged files; optionally select one hook ID
   * - ``ptk pre-commit check [HOOK]``
     - Run checks on all tracked files, equivalent to ``run --all-files``
   * - ``ptk pre-commit install``
     - Install or repair every configured Git hook type
   * - ``ptk pre-commit uninstall``
     - Remove pre-commit scripts and restore their saved legacy hooks
   * - ``ptk pre-commit status``
     - Inspect installation without changing anything; exit 1 when missing/unusable
   * - ``ptk pre-commit validate``
     - Validate the configuration with pre-commit's schema without running checks

Examples::

   ptk pre-commit run
   ptk pre-commit check --show-diff-on-failure
   ptk pre-commit run ruff-check --all-files
   ptk pre-commit run --file src/main.py --file "tests/example test.py"
   ptk pre-commit run --from-ref origin/main --to-ref HEAD
   ptk pre-commit check --hook-stage manual --verbose
   ptk firmware pre-commit status

``--file`` is repeatable; paths are relative to the repository root and must stay
inside it. File selection, ``--all-files`` and a ref pair are mutually exclusive;
``--from-ref`` and ``--to-ref`` must be supplied together. ``--hook-stage`` supports
``pre-commit``, ``pre-push`` and ``manual``. Hook output is streamed, and failed
checks retain pre-commit's nonzero exit code. Hooks may format or otherwise modify
files; ``check`` is not a dry run.

Explicit commands honor ``configs.pre-commit.output`` even when automatic
installation is disabled. Without an entry, they use ``.pre-commit-config.yaml``.
Checks and validation may prepare the managed pre-commit runtime, but do not
install Git hook scripts. Checks work on CI and with a custom ``core.hooksPath``;
install/uninstall refuse that setting to preserve existing hook management.
Uninstall leaves the runtime and caches available for future checks. Linked
worktrees share Git hook scripts, so installation/removal affects those worktrees.
If ``configs.pre-commit.enabled`` is true, the next local job installs hooks again.

These commands do not regenerate configuration or change hook revisions.
Maintainers change the owning project configuration file and run
``ptk setup configs sync pre-commit``; PTK upgrades supply newer base revisions.
``ptk setup configs check pre-commit`` checks whether the generated file is current.
Use ``command_audience: {pre-commit: maintainer}`` to restrict the whole group.
The VS Code extension discovers these built-ins automatically after updating PTK
and refreshing projects.

Variant matrices
----------------

``ptk build --all-variants`` runs every concrete variant sequentially.
``ptk -V small,large build`` selects a subset, deduplicating aliases. All selections
are prepared before the first run; each receives its own logs and report. Failures
produce an overall nonzero exit code; cancellation stops the remaining selection.
The same selection works with ``dry-run``.

``--feature SIZE=4`` (legacy ``-bo SIZE=4``) overrides a feature for this invocation.
Global ``--set vh.SIZE=4`` is also supported. ``-mp jobs=4`` is the compatibility
spelling for declared job parameters. Generated typed options take precedence
when both spellings supply a value. These overrides do not edit configuration files.

Virtual monorepositories (VMR)
------------------------------

A ``.repo`` directory in the current directory activates VMR mode. From inside
a repository, ptk finds its root and resolves that root's ``.git`` symlink,
junction or ``gitdir:`` file. A target inside a workspace's ``.repo`` directory
establishes membership, including nested project paths and git-repo worktrees.
An ordinary Git directory or worktree does not establish membership. Discovery
stops at the nearest repository boundary; an ancestor or parent containing
``.repo`` alone is not enough.

Git-repo members come from ``.repo/project.list``. A missing index is an error
with ``repo sync`` guidance. There is no recursive filesystem scan or manifest
parsing fallback, and a git-repo workspace does not need a root PTK file.

For a manual VMR, place a ``.main.ptk.yml`` containing only
``virtual_monorepo: true`` at the **workspace root**. The containing directory
is the workspace, not its parent. By default only direct child directories are
checked. To select nested repositories or a subset, list exact relative paths::

   virtual_monorepo: true
   members:
     - firmware/core
     - bootloader

``members: []`` selects no repositories. Only members with a root
``.main.ptk.yml`` participate. Symlinked directories are excluded from automatic
child discovery; explicit paths must resolve inside the workspace. Duplicate
aliases and paths outside the workspace fail discovery. If a manual marker and
``.repo`` coexist, the git-repo index takes precedence.

A repository can explicitly opt out with ``virtual_monorepo: false`` in its
own entry file; it is then standalone and excluded from the workspace listing.
Omit the field for automatic membership. Discovery fields must be literal YAML
in the entry file; fragments and CLI overrides cannot supply or change
them. Discovery reads entry metadata without loading unselected repositories'
includes. Metadata and the member index are cached for one invocation and shared
by routing, credentials and version dependencies; the next invocation rereads them.

Commands are grouped under the configured repository alias::

   ptk --help
   ptk firmware --help
   ptk firmware build
   ptk firmware setup install
   ptk bootloader variant list
   ptk --set vars.mode=debug firmware build

For git-repo members, the same grouping applies from a member's subdirectory.
Manual VMR commands are invoked from the marked workspace; inside an ordinary
member repository, ptk remains standalone. Each repository has
isolated configuration, tools, plugins, permissions and output directories.
``ptk firmware`` runs that repository's default job; bare ``ptk`` lists the
repositories. There is no implicit run across all repositories. Global options
precede the alias. ``ptk --config path/to/.main.ptk.yml build`` explicitly selects
standalone mode. Generated VS Code tasks in VMR mode include the repository alias.

Shared VMR commands
-------------------

Alongside repository aliases, the VMR root exposes ``repos``, ``help``,
``setup init``, ``setup config show/validate/schema``, ``setup doctor``, ``setup creds``,
``variant list/check`` and ``report list/summary``. ``report list --history``
includes retained historical runs. Configuration and variant output is labelled
by repository; projects without variants are skipped. Doctor checks the host
once and then each repository. There is no root ``setup install``.

Credentials with identical definitions and names are combined. Different
definitions use ``ALIAS/NAME`` at the workspace level. Provisioning a shared
credential writes once; testing it runs its configured test separately in each
owning repository. Restricted credential groups are excluded from the shared
catalog. Repository commands remain available for all these operations.

VMR credential storage is namespaced by workspace location and definition
identity unless ``credentials.NAME.namespace`` explicitly sets a stable scope.
Git-pointer membership preserves this scope even with explicit ``--config``.
Manual VMR members receive workspace scope when routed from the marked workspace;
direct standalone invocation does not infer a parent workspace. Identical definitions
share a scope; conflicting definitions cannot overwrite each other in the vault
or keyring. Moving a workspace or changing a definition changes its automatic
scope: provision again or configure a stable namespace. Explicit env and gopass
mappings are honored and may intentionally share external storage. Default env
variable names are shown by ``setup creds list``.

Listing only reads environment values and provider availability. Other stores
are labelled as unverified; listing never retrieves values or unlocks a vault.
Writes are locked read-modify-write transactions. A stale lock after a killed
process produces a diagnostic; remove it only after confirming the owner exited.

Report inputs are snapshotted with completed run summaries. Later runs start
with fresh report input directories. Historical export reads its retained
snapshot, not current inputs. Runs for the same job/variant are serialized
by a local lock; different jobs or repositories may run concurrently.

Version commands
----------------

``ptk version show/check/generate`` discovers versions and optionally writes an
ignored snapshot. There are no bump/set/tag commands. In VMR mode use
``ptk ALIAS version ...``. See :doc:`versioning` for sources and generators.

``ptk setup init`` requires a configuration directory supplied by the user.
Enter it at the terminal prompt or pass ``--config-dir PATH``; there is no
default. Scripts and ``--yes`` require the option. The path is relative to each
repository root. Root metadata stays minimal; initial
configuration documents follow the fixed layout under PATH. ``jobs/hello.ptk.yml``
and ``jobs/build.ptk.yml`` provide separate runnable examples. Optional fields
are documented in comments. Existing files are never overwritten.

In VMR mode, omit DIRECTORY to initialize **all checked-out members without a
root .main.ptk.yml**. This works before any member has PTK configuration and from
a git-repo member's subdirectory. Existing entry files are skipped, even when
their configuration is invalid, and the workspace root is not scaffolded.
Running the command again skips the newly configured repositories::

   ptk setup init --config-dir config/ptk --dry-run
   ptk setup init --config-dir config/ptk --yes
   ptk repos
   ptk firmware setup config validate

The configuration directory is prompted once and applied relative to each new
repository root: ``config/ptk`` becomes ``<repo>/config/ptk`` in every new member,
regardless of the invocation directory. When all members are configured, the
command reports skips without prompting. Generated aliases avoid existing aliases and workspace command names;
duplicate folder names use relative paths and numeric suffixes as needed.
Output identifies each initialized or skipped member and prints a final count.
``--name`` is available only with an explicit single-project DIRECTORY in VMR mode.

Git-repo initialization uses every path in ``.repo/project.list``, including
unconfigured members. Entries not checked out are reported and skipped without
creating checkout directories. Manual workspaces use their explicit ``members``
list, or direct child directories with ``.git`` or ``.main.ptk.yml``; unrelated
folders such as build outputs are not initialized. Discovery does not recurse.

``--dry-run`` previews all new configurations without writing anything. All new
members are preflighted before writing, so an existing scaffold fragment blocks
the batch without overwriting it or partly initializing other members. A later
write failure can leave earlier members initialized; rerunning skips those members.
Existing ``.gitignore`` content is preserved, with only missing rules appended.

An explicit DIRECTORY always selects one project, even from inside a VMR::

   ptk setup init path/to/new-repository --name firmware --config-dir config/ptk --yes

Outside VMR mode, omitting DIRECTORY continues to initialize the current directory.

Cleaning and re-running
-----------------------

Global options precede the command (and a VMR repository alias)::

   ptk -V debug --clean build
   ptk -V debug,release -c build
   ptk -V debug --re-run build
   ptk -V debug -rr firmware workflow run verify
   ptk -V debug --clean dry-run build
   ptk -V debug --re-run workflow dry-run verify

``--clean`` / ``-c`` deletes the selected jobs' folders in all four output
categories (binaries, builds, logs and reports), then stops. ``--re-run`` / ``-rr``
deletes the same folders, then executes. They are mutually exclusive and apply to
jobs and workflows. Clean-only does not install tools/hooks, resolve credentials,
run version commands or require job parameter values. Re-run preflights execution
before deletion. Workflow cleanup covers every referenced job in its resolved
repository and variant, deduplicating repeated calls. Job/step execution filters
still apply; a disallowed job variant is a configuration error, not a silent skip.

``clean-all`` removes the repository's complete output folders across every job
and variant. At a VMR root, select a repository or explicitly clean the workspace::

   ptk clean-all
   ptk firmware clean-all
   ptk vmr-clean-all
   ptk clean-all --dry-run
   ptk vmr-clean-all --yes

Both all-clean commands list the directories and ask for confirmation; ``--yes``
(or ``-y``) skips the prompt. ``vmr-clean-all`` includes all configured member
repositories and the VMR root's default output folders (including workspace
workflow reports). Job/workflow clean and re-run do not prompt. Dry-run modes
never delete folders. PTK preflights all paths before deletion and refuses
repository roots, paths outside repositories, symlink paths, configuration/Git
metadata, tracked source files and active job locks. Filesystem errors can still
interrupt deletion; cleanup is not a transactional filesystem operation.

Migration: ``--config`` now uses uppercase ``-C``. Lowercase ``-c`` means clean.
Binary output paths now include the job: ``_bin/<variant>/<job>``. Jobs using
``${run.bin_dir}`` receive the new path automatically; update hard-coded paths.
Old files directly under ``_bin/<variant>`` remain until ``clean-all``.

PTK cleanup versus native build-tool cleanup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PTK deletes output directories. It does not invoke Bazel or CMake's clean targets.
Arguments after ``--`` are forwarded to job steps marked ``passthrough: true``;
``--args-for STEP="ARGS"`` targets a particular eligible step. PTK options must
appear before the job; forwarded arguments appear after it.

For a CMake build job with a passthrough step running ``cmake --build build``, use::

   ptk build -- --target clean
   ptk build -- --clean-first

Bazel's ``clean`` is a subcommand, not a ``-clean`` flag. Configure a dedicated
job, for example::

   # config/ptk/jobs/bazel-clean.ptk.yml
   steps:
   - clean:
       run:
       - bazel
       - clean
       passthrough: true

Then ``ptk bazel-clean`` invokes native ``bazel clean`` and
``ptk bazel-clean -- --expunge`` invokes ``bazel clean --expunge``. Appending
``clean`` to a job running ``bazel build`` does not switch its subcommand.
Native cleanup scope is controlled by the build tool and its working directory;
it is independent of PTK's selected-job folder cleanup.
