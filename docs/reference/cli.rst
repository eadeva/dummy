CLI command groups
==================

PTk separates everyday work, local self-service and project maintenance.
PTk uses CX for automated test and development execution: ``--cx`` /
``--no-cx``, environment override ``PTK_CX``, and condition symbol ``cx``.
These replace the former CI-named PTk interfaces; legacy aliases are not accepted.
Update existing scripts and conditions when upgrading. Standard provider variables
such as ``CI``, ``GITHUB_ACTIONS`` and ``GITLAB_CI`` still automatically detect
hosted execution; ``PTK_CX`` overrides that detection.
Jobs and workflows are both direct commands: ``ptk build`` and ``ptk verify``.
Use ``ptk maintainer NAME`` for jobs and workflows declared with
``audience: maintainer``. If a job and workflow share a name, choose explicitly
with ``run NAME`` or ``workflow run NAME`` within the same namespace.

Help shows Jobs, Workflows, everyday Commands, Self-service and Maintenance in
that order. At a VMR root, a **VMR commands** panel comes first and Repositories
replaces Jobs. Maintenance is visible
to maintainers listed by the owning project or workspace. CX also permits
entry to the maintenance namespace for the hidden, read-only matrix export;
other maintenance commands retain their role checks. Group help and Tab
completion follow the same permissions and ordering.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Command
     - Purpose
   * - ``ptk maintainer gen-workflows [NAMES...]``
     - Generate callable GitHub workflow templates without overwriting existing files
   * - ``ptk init [DIRECTORY]``
     - Create project configuration, or initialize missing VMR members; no existing project or maintainer role is required
   * - ``ptk NAME [--dry-run]``
     - Run or preview a project job or workflow
   * - ``ptk variant list|show|explain``
     - Inspect the product line and explain resolved feature values
   * - ``ptk validate [--variants] [--versions] [--generated]``
     - Validate PTk configuration; optionally check concrete variants, version sources or generated shared configuration
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
   * - ``ptk self-service creds setup|set|list|test|remove|lock|reset``
     - Manage the credential vault and stored values (``lock`` ends the unlocked session, ``reset`` deletes the vault)
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
   * - ``ptk maintainer sync configs|agent [--check|--force]``
     - Regenerate one explicitly selected integration, or check it without writing
   * - ``ptk maintainer configs-report [--output PATH]``
     - Write offline JSON deviations and modified external-base filenames; does not synchronize files
   * - ``ptk maintainer version show|generate``
     - Inspect discovered versions or generate a version snapshot
   * - ``ptk maintainer artifacts destination --job JOB``
     - Resolve an artifact destination for external upload automation
   * - ``ptk maintainer matrix [--job JOB] [--format json|github]``
     - Hidden setup export of eligible variants/jobs, argv, version/source commit and upload bases; available to maintainers and CX, see :doc:`/guides/cx-matrix`
   * - ``ptk maintainer NAME [--dry-run]``
     - Run or preview a maintainer job or workflow

``self-service`` and ``maintainer`` without a subcommand show help without
changing files. ``maintainer sync`` requires a target; it never generates
unrequested integrations. Config names may follow ``sync configs``;
``--diff`` previews shared configuration changes. Both targets support ``--check``.
Both also support ``--force``: locally changed or unowned files that would
otherwise block the sync are listed, and they are overwritten only when the
maintainer confirms the prompt. Declining writes nothing; CX refuses ``--force``.
``--force`` cannot be combined with ``--check`` or ``--diff``.
At a VMR root the option is forwarded to every member, each with its own prompt.
``sync agent`` installs the PTk expert agent, its skills and offline reference docs.

``validate`` is always available. With no project it reports
"No PTk project found" and suggests ``ptk init``. Ordinary validation only
loads local configuration. ``--variants --strict`` treats variant warnings as
errors; ``--versions`` opts into version discovery and accepts ``--job`` for
explicit version dependencies. ``--generated`` checks shared configuration
without writing and is available to CX users without maintenance permissions.

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
extension does not infer command routing. Update PTk and its bundled extension
together when upgrading this command interface.

Terminal Tab completion
-----------------------

PTk is installed once per user and works without activating a project virtual
environment. Completion is a shell feature: both installers persist it for
Bash/Git Bash and every detected PowerShell edition. For an existing installation,
install or repair all registrations with::

   ptk self-service completion install

This locates the shared launcher using ``uv tool dir --bin`` rather than an
activated venv's PTk. ``--executable PATH`` explicitly selects another shared
launcher. Each shell profile adds that tool directory to PATH if needed,
including new VS Code terminals that inherit an older environment. An explicitly
activated development environment keeps precedence. No Python process starts
when a shell opens; PTk runs only when completion is requested.

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

To complete job options, type ``ptk JOB --`` and press Tab (twice to list
multiple matches in shells using that binding). Bare ``ptk JOB `` followed by Tab
does not list option names: option completion starts with ``-``. After a choice
option, Tab completes its allowed values, for example ``ptk JOB --build-type D``.
Use ``ptk JOB --help`` for all options and descriptions. If even ``--`` produces
no suggestions, install/load completion for the active shell and open a new
terminal; check that its PATH selects the intended PTk installation.

To target just one PowerShell profile instead of all shells::

   ptk self-service completion powershell --double-tab --install $PROFILE.CurrentUserAllHosts

This updates one marked PTk block, preserves the rest of the profile and its
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
available for the double-Tab binding; the PTk completer itself does not require it.
PTk normalizes an unfinished bare ``--`` in PowerShell completion independently
of the command AST's element count. A trailing space still commits ``--`` as the
end-of-options marker; the registration script preserves that boundary even
though PowerShell removes trailing whitespace from its command AST. After updating
PTk, regenerate the persistent registration and reload it in any already-open
terminal. Native ``TabExpansion2`` tests cover both forms, option prefixes and
choice values. Windows PowerShell 5.1 never calls native completers for a bare
``--``; type the first letter of the option (``--b``) or use PowerShell 7.

To check candidate generation independently of the Tab key binding, replace
``JOB`` below with a configured job name and run::

   $line = 'ptk JOB --'
   (TabExpansion2 $line $line.Length).CompletionMatches | Select-Object CompletionText

If this lists options but Tab does not, check the PSReadLine binding. If it
returns nothing, check ``Get-Command ptk -All`` and ``ptk --version``, then reload
the completion registration from that executable. Updating a checkout alone
does not update a separately installed PTk package or a saved profile script.
Generating a script without ``--install`` does not modify the profile.
Profile loading must be allowed by your PowerShell execution policy; PTk does
not change that policy. Terminals started with ``-NoProfile`` do not load it.

To remove permanent completion, remove only the managed PTk block with::

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

Zsh and Fish registration remains explicit. Traditional ``cmd.exe`` can run PTk
but does not use these completion scripts. Shells started with profile loading
disabled also need explicit registration. WSL/SSH/container environments need
their own PTk installation and shell setup on the workspace host.

Examples (``<Tab>`` means press the key)::

   ptk <Tab><Tab>                   # available commands, jobs and workflows
   ptk build --<Tab><Tab>           # options for the configured build job
   ptk build --build-type <Tab>     # declared choice values
   ptk --variant <Tab><Tab>         # concrete variants and aliases
   ptk build --only-step <Tab><Tab> # step IDs
   ptk build --to <Tab><Tab>        # inclusive final step
   ptk build --feature MODE=<Tab>   # declared enum/bool feature values
   ptk build --args-for <Tab>       # eligible passthrough step paths
   ptk workflow run <Tab><Tab>      # available workflow names

Job names also complete after ``run``, report commands and ``--job`` options.
VMR completion includes repository aliases and repository-qualified workflows.
Suggestions respect command visibility and the current project configuration;
integration commands remain hidden from ordinary help. The maintainer namespace
is unavailable to ordinary local users; CX has the narrow matrix-export exception
described above.
Type ``-`` to request option names. Choice and path parameters use native shell
completion; free-text and secret values are not guessed.

``ptk --help`` also lists available concrete variants and aliases beside
``--variant``. ``ptk JOB --help`` lists the job's top-level step names beside
``--only-step`` and ``--to``, in authored order. Long lists show the first 12 values;
Tab completion offers the complete set. These hints use the same project metadata
as the extension's run-options form. ``--only-step``/``--to`` apply to jobs; workflows
select one owner variant and use their configured job mappings.

Each completion request starts a short-lived PTk process and reads the required
configuration. It does not execute jobs, load Python tools, resolve Git/version
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
and workflow list/show. ``workflow list`` shows workflows for everyone;
``maintainer workflow list`` shows all workflows, marking maintainer-only ones.
Workflow execution selects the owner variant and resolves
other repositories through its ``repo_variants`` mappings.
The option is no longer accepted after a job or subcommand.

``--cx`` / ``--no-cx`` is maintainer-only: hidden from user help and completion,
and rejected on direct invocation. With neither flag, CX detection works for all
users. In a VMR, a repository-qualified command checks that member's maintainer
list; workspace commands check the root list. Member operations also enforce
their own permissions. The default mode remains automatically detected.

``variant list``, ``show`` and ``explain`` are read-only. Edit the YAML
configuration directly to change the product line or configured default.
Persistent variant editing commands and the desktop editor have been removed.

Pre-commit commands
-------------------

The built-in ``pre-commit`` group uses the current repository's configured
pre-commit file and PTk's managed runtime. No separate pre-commit executable on
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

Explicit commands honor ``configs.pre-commit.hook_config`` even when automatic
installation is disabled. Without an entry, they use ``.pre-commit-config.yaml``.
Checks and validation may prepare the managed pre-commit runtime, but do not
install Git hook scripts. Checks work on CX and with a custom ``core.hooksPath``;
install/uninstall refuse that setting to preserve existing hook management.
Uninstall leaves the runtime and caches available for future checks. Linked
worktrees share Git hook scripts, so installation/removal affects those worktrees.
If ``configs.pre-commit.enabled`` is true, the next local job installs hooks again.

These commands do not regenerate configuration or change hook revisions.
Maintainers change the owning project configuration file and run
``ptk maintainer sync configs pre-commit``; PTk upgrades supply newer base revisions.
``ptk maintainer sync configs --check pre-commit`` checks whether the generated file is current.
Use ``command_audience: {pre-commit: maintainer}`` to restrict the whole group.
The VS Code extension discovers these built-ins automatically after updating PTk
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
parsing fallback, and a git-repo workspace does not need a root PTk file.

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
isolated configuration, tools, permissions and output directories.
``ptk firmware`` runs that repository's default job; bare ``ptk`` lists the
repositories. Jobs never run across all repositories implicitly; the shared
commands below act on every repository. Global options
precede the alias. Project selection uses the working directory and the repository
alias; there is no global ``--config``/``-C`` option. To opt a repository out of
VMR membership, set ``virtual_monorepo: false`` in its root marker. Extension
launches use the discovered workspace directory
and repository alias.

.. _vmr-commands:

Shared VMR commands
-------------------

Alongside repository aliases, the VMR root exposes commands that act on every
PTk repository of the workspace. ``ptk --help`` lists them first in the
**VMR commands** panel (maintenance entries only for workspace maintainers):

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Command
     - Effect
   * - ``ptk jobs``
     - List ``ALIAS/JOB: help`` for every repository; marks ``(gui)`` and, for that
       repository's maintainers, ``(maintainer)`` jobs
   * - ``ptk validate``, ``ptk variant list``, ``ptk report list|summary``
     - Validate, list variants or show recorded runs of every repository
   * - ``ptk self-service doctor``
     - Check the host once, then each repository
   * - ``ptk self-service tools [--job JOB] [--dry-run]``
     - Check and install tools in every repository; with ``--job`` only in
       repositories defining that job (an error if none does)
   * - ``ptk self-service hooks install|uninstall|status``
     - Manage Git hooks in every repository that has a pre-commit configuration
   * - ``ptk self-service creds ...``
     - Combined credentials (see below); ``lock`` and ``reset`` act once on your vault
   * - ``ptk maintainer sync configs|agent``, ``maintainer config show``,
       ``maintainer configs-report``, ``maintainer version show``
     - Maintenance in every repository; refused before any repository runs if
       you are not a maintainer of each one
   * - ``ptk help``
     - Open the advanced HTML help of the whole VMR (see below)
   * - ``ptk repos``, ``ptk init``, ``ptk vmr-clean-all``
     - List members, initialize unconfigured members, clean all outputs

Each repository prints a ``[ALIAS]`` header. A failure in one repository does not
stop the others; the command exits with the worst exit code. Configuration and
variant output is labelled by repository; projects without variants are skipped.
``report list --history`` includes retained historical runs. Inside a member
directory, member-specific commands such as ``self-service tools`` act on that
member; ``jobs`` and the workspace ``self-service`` commands (``completion``,
``extension``, ``doctor``, ``creds``) keep their workspace meaning.

Advanced HTML help
------------------

``ptk help`` writes a self-contained HTML page (``.ptk/help.html``, or ``-o PATH``)
and opens it unless ``--no-open`` is given. Its navigation follows the VS Code
extension: **Jobs**, **GUIs** and **Workflows** (expanded), **Built-in commands**
nested by command path (for example *self-service › creds › set*),
**Configuration** (variants, credentials, tools, files) and **AI assistant**,
which explains the ``ptk-expert`` agent, lists the bundled skills and shows
whether ``ptk maintainer sync agent`` installed them. Jobs and workflows include
their dependency graphs. The page uses the full browser width. Search filters the page and
opens matching branches. Maintainer-only jobs and workflows appear only for
maintainers. At a VMR root the page starts with the VMR commands, workspace
workflows and the assistant, followed by one branch per repository with the
same groups and that repository's role.

Credentials with the same name are combined: the vault belongs to the user and
is shared by every project and repository. Provisioning a credential writes
once; testing it runs its configured test separately in each owning repository.
Restricted credential groups are excluded from the shared catalog. Repository
commands remain available for all these operations.

Vault entries are keyed by ``NAME.FIELD`` only. Values stored by older PTk
versions under a VMR scope are moved to that key when they are unambiguous.
Explicit env mappings are honored and may intentionally share variables. Default env
variable names are shown by ``self-service creds list``.

Listing only reads environment values and provider availability. Other stores
are labelled as unverified; listing never retrieves values or unlocks a vault.
Writes are locked read-modify-write transactions. A stale lock after a killed
process produces a diagnostic; remove it only after confirming the owner exited.

Report inputs are snapshotted with completed run summaries. Later runs start
with fresh report input directories. Historical export reads its retained
snapshot, not current inputs. A local lock rejects concurrent runs for the same job/variant; different jobs
or repositories may run concurrently.

Version commands
----------------

``ptk maintainer version show/generate`` discovers versions and optionally writes an
ignored snapshot. There are no bump/set/tag commands. In VMR mode use
``ptk ALIAS maintainer version ...``. See :doc:`/guides/versioning` for sources and generators.

``ptk init`` requires a configuration directory supplied by the user.
Enter it at the terminal prompt or pass ``--config-dir PATH``; there is no
default. Scripts and ``--yes`` require the option. The path is relative to each
repository root. Root metadata stays minimal; initial
configuration documents follow the fixed layout under PATH. ``jobs/hello.ptk.yml``
and ``jobs/build.ptk.yml`` provide separate runnable examples. Optional fields
are documented in comments. Init also writes a generated ``README.md`` under PATH
and installs the expert agent, 16 project-facing skills, offline references and
schema under ``.github``. Links in the README are relative to the chosen config
directory. The README, configuration and assistant files are protected by preflight. Dry-run writes nothing. Use
``ptk maintainer sync agent`` for later managed README and bundle updates. README provenance is stored
in ``.github/ptk/manifest.json``; unchanged generated files update automatically,
while local edits or different unowned files cause conflicts. ``--check`` includes
the README. A changed config path relocates an unmodified managed README and
rebuilds its relative links; modified old files must be reconciled first or
replaced with a confirmed ``--force``.

In VMR mode, omit DIRECTORY to initialize **all checked-out members without a
root .main.ptk.yml**. This works before any member has PTk configuration and from
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
repository and variant, deduplicating identical output paths. Job/step execution filters
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
never delete folders. PTk preflights all paths before deletion and refuses
repository roots, paths outside repositories, symlink paths, configuration/Git
metadata, tracked source files and active job locks. Filesystem errors can still
interrupt deletion; cleanup is not a transactional filesystem operation.

Lowercase ``-c`` means clean.
Binary output paths now include the job: ``_bin/<variant>/<job>``. Jobs using
``${run.bin_dir}`` receive the new path automatically; update hard-coded paths.
Old files directly under ``_bin/<variant>`` remain until ``clean-all``.

PTk cleanup versus native build-tool cleanup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PTk deletes output directories. It does not invoke Bazel or CMake's clean targets.
Arguments after ``--`` are forwarded to job steps marked ``passthrough: true``;
``--args-for STEP="ARGS"`` targets a particular eligible step. PTk options must
appear before the job; forwarded arguments appear after it.

For a CMake build job with a passthrough step running ``cmake --build build``, use::

   ptk build -- --target clean
   ptk build -- --clean-first

Bazel's ``clean`` is a subcommand, not a ``-clean`` flag. Configure a dedicated
job, for example::

   steps:
     clean:
       run:
       - bazel
       - clean
       passthrough: true

Then ``ptk bazel-clean`` invokes native ``bazel clean`` and
``ptk bazel-clean -- --expunge`` invokes ``bazel clean --expunge``. Appending
``clean`` to a job running ``bazel build`` does not switch its subcommand.
Native cleanup scope is controlled by the build tool and its working directory;
it is independent of PTk's selected-job folder cleanup.
