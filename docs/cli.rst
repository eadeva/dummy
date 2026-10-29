CLI command groups
==================

PTK separates everyday work, local self-service and project maintenance.
Jobs and workflows are both direct commands: ``ptk build`` and ``ptk verify``.
Use ``ptk maintainer NAME`` for jobs and workflows declared with
``audience: maintainer``. If a job and workflow share a name, choose explicitly
with ``run NAME`` or ``workflow run NAME`` within the same namespace.

Help shows Jobs, Workflows, everyday Commands, Self-service and Maintenance in
that order. At a VMR root, Repositories replaces Jobs. Maintenance is visible
only to maintainers listed by the owning project or workspace. Group help and
Tab completion follow the same permissions and ordering.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Command
     - Purpose
   * - ``ptk init [DIRECTORY]``
     - Create project configuration, or initialize missing VMR members; no existing project or maintainer role is required
   * - ``ptk NAME [--dry-run]``
     - Run or preview a project job or workflow
   * - ``ptk variant list|show|explain``
     - Inspect the product line and explain resolved feature values
   * - ``ptk validate [--variants] [--versions] [--generated]``
     - Validate PTK configuration; optionally check concrete variants, version sources or generated shared configuration
   * - ``ptk report open JOB`` / ``ptk report open --workflow NAME``
     - Open the latest saved job or workflow report
   * - ``ptk report export JOB``
     - Regenerate a job report from recorded results
   * - ``ptk pre-commit run [--all-files]`` / ``ptk pre-commit validate``
     - Run repository checks or validate the pre-commit configuration
   * - ``ptk clean-all``
     - Remove project outputs, with confirmation
   * - ``ptk self-service tools``
     - Install missing or outdated tools; optionally select ``--job JOB`` or preview with ``--dry-run``
   * - ``ptk self-service creds setup|set|list|test|remove``
     - Manage personal credential providers and stored values
   * - ``ptk self-service completion install|powershell|bash|zsh|fish``
     - Persist or generate shell completion, even outside a project
   * - ``ptk self-service extension``
     - Install or export the bundled VS Code extension, even outside a project
   * - ``ptk self-service doctor``
     - Diagnose the local environment and project
   * - ``ptk self-service hooks install|uninstall|status``
     - Manage this repository's local Git hooks
   * - ``ptk maintainer config show|schema``
     - Inspect effective configuration and sources, or export its JSON schema
   * - ``ptk maintainer sync configs|tasks|agent [--check]``
     - Regenerate one explicitly selected integration, or check it without writing
   * - ``ptk maintainer version show|generate``
     - Inspect discovered versions or generate a version snapshot
   * - ``ptk maintainer artifacts destination --job JOB``
     - Resolve an artifact destination for external upload automation
   * - ``ptk maintainer NAME [--dry-run]``
     - Run or preview a maintainer job or workflow

``self-service`` and ``maintainer`` without a subcommand show help without
changing files. ``maintainer sync`` requires a target; it never generates
unrequested integrations. Config names may follow ``sync configs``;
``--diff`` previews shared configuration changes. Tasks accept ``--command``,
``--users-only`` and ``--output``. Agent resources and tasks both support ``--check``.
``sync agent`` installs the PTK expert agent, its skills and offline reference docs.

``validate`` is always available. With no project it reports
"No PTK project found" and suggests ``ptk init``. Ordinary validation only
loads local configuration. ``--variants --strict`` treats variant warnings as
errors; ``--versions`` opts into version discovery and accepts ``--job`` for
explicit version dependencies. ``--generated`` checks shared configuration
without writing and is available to CI users without maintenance permissions.

Global options precede commands and repository aliases::

   ptk -V debug build --dry-run
   ptk -V debug verify --dry-run
   ptk firmware maintainer publish --dry-run
   ptk self-service tools --job build --dry-run
   ptk maintainer sync configs --check

There are no legacy command aliases. The previous ``setup`` group, standalone
``dry-run``, ``self-setup``, and top-level configuration/tooling aliases have
been removed. Previews use ``--dry-run``; the flag also works with generic
``run NAME --param KEY=VALUE`` and explicit ``workflow run NAME``.

``run`` remains a supported generic job interface for scripts, and
``describe --json --configuration`` provides the versioned extension interface.
Both are hidden from normal help and completion. The inventory supplies the
exact job/workflow command paths, including the maintainer namespace, so the
extension does not infer command routing. Update PTK and its bundled extension
together when upgrading this command interface.

Terminal Tab completion
-----------------------

PTK is installed once per user and works without activating a project virtual
environment. Completion is a shell feature: both installers persist it for
Bash/Git Bash and every detected PowerShell edition. For an existing installation,
install or repair all registrations with::

   ptk self-service completion install

This locates the shared launcher using ``uv tool dir --bin`` rather than an
activated venv's PTK. ``--executable PATH`` explicitly selects another shared
launcher. Each shell profile adds that tool directory to PATH if needed,
including new VS Code terminals that inherit an older environment. An explicitly
activated development environment keeps precedence. No Python process starts
when a shell opens; PTK runs only when completion is requested.

On Windows, setup queries Windows PowerShell and PowerShell 7 separately for
their ``$PROFILE.CurrentUserAllHosts`` paths, including redirected Documents
folders. It also discovers Git Bash's home when Git Bash is installed. On Linux,
Bash uses the user's home. Bash registration is loaded by ``.bashrc`` and the
first existing login file (``.bash_profile``, ``.bash_login`` or ``.profile``).
If none exists, setup creates ``.bash_profile``. The actual generated script is
stored in ``~/.local/share/ptk/completion.bash``; the profile loader is safe for
POSIX shells that also read ``.profile``.

All managed blocks are checked before writes. Existing settings, encodings and
line endings are preserved, original profiles get ``.ptk.bak`` backups, and
repeated installs do not duplicate entries. No administrator rights are needed.
Running ``.\install\install.ps1`` from PowerShell also activates it in that
session. If you launch the installer in a separate process with ``powershell
-File``, open a new terminal afterwards. Use ``-NoCompletion`` (PowerShell) or
``--no-completion`` (Bash) to leave completion settings unchanged.

To target just one PowerShell profile instead of all shells::

   ptk self-service completion powershell --double-tab --install $PROFILE.CurrentUserAllHosts

This updates one marked PTK block, preserves the rest of the profile and its
encoding, and keeps a ``.ptk.bak`` backup of an existing profile before the first
change. Repeating the command updates the block without adding duplicates.
PowerShell supplies the path, including redirected Documents locations;
Windows PowerShell and PowerShell 7 have separate profiles. This single-profile
command affects only the selected profile; ``completion install`` handles all
detected editions.

Open a new terminal, or activate completion immediately in the current shell::

   ptk self-service completion powershell --double-tab | Out-String | Invoke-Expression

``--double-tab`` uses PSReadLine's ``Complete`` binding: Tab completes the unique
prefix; another Tab lists the remaining matches. This changes Tab for **all
commands** in that shell. Omit the flag to keep your current key bindings
(Windows PowerShell normally cycles matches with Tab). PSReadLine must be
available for the double-Tab binding; the PTK completer itself does not require it.
Generating a script without ``--install`` does not modify the profile.
Profile loading must be allowed by your PowerShell execution policy; PTK does
not change that policy. Terminals started with ``-NoProfile`` do not load it.

To remove permanent completion, remove only the managed PTK block with::

   ptk self-service completion powershell --uninstall $PROFILE.CurrentUserAllHosts

Then open a new terminal. Removal does not reset bindings already active in the
current session or remove activation lines you previously added by hand.

For Bash (4.4 or later), enable completion with::

   eval "$(ptk self-service completion bash)"

Use ``ptk self-service completion install`` for future Bash terminals. Bash normally
lists multiple matches on the second Tab. For Zsh, after your usual ``compinit`` initialization::

   eval "$(ptk self-service completion zsh)"

For Fish::

   ptk self-service completion fish | source

You can save a generated script with ``--output PATH`` and source that file from
your shell profile instead. Its directory must already exist. Zsh and Fish use
their configured completion key bindings and display styles.

Zsh and Fish registration remains explicit. Traditional ``cmd.exe`` can run PTK
but does not use these completion scripts. Shells started with profile loading
disabled also need explicit registration. WSL/SSH/container environments need
their own PTK installation and shell setup on the workspace host.

Examples (``<Tab>`` means press the key)::

   ptk <Tab><Tab>                   # available commands, jobs and workflows
   ptk build --<Tab><Tab>           # options for the configured build job
   ptk build --build-type <Tab>     # declared choice values
   ptk --variant <Tab><Tab>         # concrete variants and aliases
   ptk build --from <Tab><Tab>      # top-level step names
   ptk build --to <Tab><Tab>        # inclusive final step
   ptk build --feature MODE=<Tab>   # declared enum/bool feature values
   ptk build --args-for <Tab>       # eligible passthrough step paths
   ptk workflow run <Tab><Tab>      # available workflow names

Job names also complete after ``run``, report commands and ``--job`` options.
VMR completion includes repository aliases and repository-qualified workflows.
Suggestions respect command visibility and the current project configuration;
integration commands and the maintainer namespace remain hidden from ordinary users.
Type ``-`` to request option names. Choice and path parameters use native shell
completion; free-text and secret values are not guessed.

``ptk --help`` also lists available concrete variants and aliases beside
``--variant``. ``ptk JOB --help`` lists the job's top-level step names beside
``--from`` and ``--to``, in execution order. Long lists show the first 12 values;
Tab completion offers the complete set. These hints use the same project metadata
as the extension's run-options form. ``--from``/``--to`` apply to jobs; workflows
select one owner variant and use their configured job mappings.

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
   ptk -V debug build --dry-run
   ptk -V debug firmware build
   ptk -V debug variant show
   ptk -V debug report open build

It selects the variant for jobs, version discovery/generation, report commands,
artifact destinations and ``variant show`` when NAME is omitted. An explicit
NAME on ``variant show`` takes precedence. It is irrelevant to self-service/config/help/pre-commit,
variant list/explain (which have their own explicit selection), describe,
and workflow list/show. Workflow execution selects the owner variant and resolves
other repositories through its ``repo_variants`` mappings.
The option is no longer accepted after a job or subcommand.

``--ci`` / ``--no-ci`` is maintainer-only: hidden from user help and completion,
and rejected on direct invocation. With neither flag, CI detection works for all
users. In a VMR, a repository-qualified command checks that member's maintainer
list; workspace commands check the root list. Member operations also enforce
their own permissions. The default mode remains automatically detected.

``variant list``, ``show`` and ``explain`` are read-only. Edit the YAML
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
   * - ``ptk pre-commit run --all-files [HOOK]``
     - Run checks on all tracked files, equivalent to ``run --all-files``
   * - ``ptk self-service hooks install``
     - Install or repair every configured Git hook type
   * - ``ptk self-service hooks uninstall``
     - Remove pre-commit scripts and restore their saved legacy hooks
   * - ``ptk self-service hooks status``
     - Inspect installation without changing anything; exit 1 when missing/unusable
   * - ``ptk pre-commit validate``
     - Validate the configuration with pre-commit's schema without running checks

Examples::

   ptk pre-commit run
   ptk pre-commit run --all-files --show-diff-on-failure
   ptk pre-commit run ruff-check --all-files
   ptk pre-commit run --file src/main.py --file "tests/example test.py"
   ptk pre-commit run --from-ref origin/main --to-ref HEAD
   ptk pre-commit run --all-files --hook-stage manual --verbose
   ptk firmware self-service hooks status

``--file`` is repeatable; paths are relative to the repository root and must stay
inside it. File selection, ``--all-files`` and a ref pair are mutually exclusive;
``--from-ref`` and ``--to-ref`` must be supplied together. ``--hook-stage`` supports
``pre-commit``, ``pre-push`` and ``manual``. Hook output is streamed, and failed
checks retain pre-commit's nonzero exit code. Hooks may format or otherwise modify
files; ``run --all-files`` is not a dry run.

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
``ptk maintainer sync configs pre-commit``; PTK upgrades supply newer base revisions.
``ptk maintainer sync configs --check pre-commit`` checks whether the generated file is current.
Use ``command_audience: {pre-commit: maintainer}`` to restrict the whole group.
The VS Code extension discovers these built-ins automatically after updating PTK
and refreshing projects.

Variant matrices
----------------

``ptk build --all-variants`` runs every concrete variant sequentially.
``ptk -V small,large build`` selects a subset, deduplicating aliases. All selections
are prepared before the first run; each receives its own logs and report. Failures
produce an overall nonzero exit code; cancellation stops the remaining selection.
The same selection works with ``--dry-run``.

``--feature SIZE=4`` overrides a feature for this invocation. Global
``--set vh.SIZE=4`` is also supported. Use generated typed job options or
``ptk run JOB --param NAME=VALUE`` for parameter overrides. These overrides do
not edit configuration files. The old ``-bo`` and ``-mp`` spellings are removed.

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
configuration files. Metadata and the member index are cached for one invocation and shared
by routing, credentials and version dependencies; the next invocation rereads them.

Commands are grouped under the configured repository alias::

   ptk --help
   ptk firmware --help
   ptk firmware build
   ptk firmware self-service tools
   ptk bootloader variant list
   ptk --set vars.mode=debug firmware build

For git-repo members, the same grouping applies from a member's subdirectory.
Manual VMR commands are invoked from the marked workspace; inside an ordinary
member repository, ptk remains standalone. Each repository has
isolated configuration, tools, plugins, permissions and output directories.
``ptk firmware`` runs that repository's default job; bare ``ptk`` lists the
repositories. There is no implicit run across all repositories. Global options
precede the alias. Project selection uses the working directory and the repository
alias; there is no global ``--config``/``-C`` option. To opt a repository out of
VMR membership, set ``virtual_monorepo: false`` in its root marker. Generated
VS Code tasks and extension launches use the discovered workspace directory
and repository alias.

Shared VMR commands
-------------------

Alongside repository aliases, the VMR root exposes ``repos``, ``help``,
``init``, ``validate``, ``maintainer config show/schema``, ``self-service doctor``, ``self-service creds``,
``variant list`` and ``report list/summary``. ``report list --history``
includes retained historical runs. Configuration and variant output is labelled
by repository; projects without variants are skipped. Doctor checks the host
once and then each repository. There is no root ``self-service tools``.

Credentials with identical definitions and names are combined. Different
definitions use ``ALIAS/NAME`` at the workspace level. Provisioning a shared
credential writes once; testing it runs its configured test separately in each
owning repository. Restricted credential groups are excluded from the shared
catalog. Repository commands remain available for all these operations.

VMR credential storage is namespaced by workspace location and definition
identity unless ``credentials.NAME.namespace`` explicitly sets a stable scope.
Git-pointer membership preserves this scope when invoked from a member directory.
Manual VMR members receive workspace scope when routed from the marked workspace;
direct standalone invocation does not infer a parent workspace. Identical definitions
share a scope; conflicting definitions cannot overwrite each other in the vault
or keyring. Moving a workspace or changing a definition changes its automatic
scope: provision again or configure a stable namespace. Explicit env and gopass
mappings are honored and may intentionally share external storage. Default env
variable names are shown by ``self-service creds list``.

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

``ptk maintainer version show/generate`` discovers versions and optionally writes an
ignored snapshot. There are no bump/set/tag commands. In VMR mode use
``ptk ALIAS maintainer version ...``. See :doc:`versioning` for sources and generators.

``ptk init`` requires a configuration directory supplied by the user.
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

   ptk init --config-dir config/ptk --dry-run
   ptk init --config-dir config/ptk --yes
   ptk repos
   ptk firmware validate

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

   ptk init path/to/new-repository --name firmware --config-dir config/ptk --yes

Outside VMR mode, omitting DIRECTORY continues to initialize the current directory.

Cleaning and re-running
-----------------------

Global options precede the command (and a VMR repository alias)::

   ptk -V debug --clean build
   ptk -V debug,release -c build
   ptk -V debug --re-run build
   ptk -V debug -rr firmware workflow run verify
   ptk -V debug --clean build --dry-run
   ptk -V debug --re-run workflow run --dry-run verify

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

Lowercase ``-c`` means clean.
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
