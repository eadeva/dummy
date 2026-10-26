CLI command groups
==================

Use ``ptk setup`` to display the setup overview. Viewing this overview does not
install tools or change configuration. Project actions remain top-level commands.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Purpose
   * - ``ptk setup init [DIRECTORY]``
     - Initialize missing VMR configs, or create one project at DIRECTORY
   * - ``ptk setup config show|validate|schema``
     - Inspect, validate and export project configuration
   * - ``ptk setup configs sync|check``
     - Generate and verify shared tool configurations
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
   * - ``ptk workflow list|show|dry-run|run``
     - Inspect or execute local action workflows (execution is disabled on CX)
   * - ``ptk ACTION`` / ``ptk run ACTION``
     - Execute project actions
   * - ``ptk dry-run ACTION``
     - Preview execution

Put global options before the group, and installation options after ``install``::

   uv run ptk -c examples/quickstart/.main.ptk.yml setup config validate
   uv run ptk -c examples/quickstart/.main.ptk.yml setup install --action build --dry-run
   uv run ptk -c examples/quickstart/.main.ptk.yml setup creds list

The ``ptk init`` alias also remains available.

The former top-level ``config``, ``configs``, ``creds``, ``self-setup``, ``doctor``
and ``vscode`` commands remain callable aliases, hidden from help and completion.
Legacy ``ptk setup --action ACTION --dry-run`` also remains supported. Bare
``ptk setup`` now shows help; use ``ptk setup install`` to install all configured
tools. Do not combine legacy installation options with a setup subcommand.

M11 commands
------------

``ptk variant gui [--plugin NAME] [--output FILE]`` opens the optional desktop
variant editor. See :doc:`m11` for prerequisites and semantics.

Variant editing and matrices
----------------------------

``ptk variant new NAME --extends BASE --feature SIZE=4`` creates a variant.
``ptk variant set NAME SIZE=5`` selects the default and optionally changes features.
Both validate first, write ``local.ptk.yml`` by default, and accept ``--dry-run``
or ``--output FILE`` for an explicit overlay. Existing unrelated YAML keys are
preserved; formatting/comments are not. Include explicit overlays yourself.

``ptk build --all-variants`` runs every concrete variant sequentially.
``ptk build -V small,large`` selects a subset, deduplicating aliases. All selections
are prepared before the first run; each receives its own logs and report. Failures
produce an overall nonzero exit code; cancellation stops the remaining selection.
The same selection works with ``dry-run``.

``--feature SIZE=4`` (legacy ``-bo SIZE=4``) overrides a feature for this invocation.
Global ``--set vh.SIZE=4`` is also supported. ``-mp jobs=4`` is the compatibility
spelling for declared action parameters. Generated typed options take precedence
when both spellings supply a value. Persistent editing refuses global config overrides.

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
in the entry file; includes, overlays and CLI overrides cannot supply or change
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
``ptk firmware`` runs that repository's default action; bare ``ptk`` lists the
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
snapshot, not current inputs. Runs for the same action/variant are serialized
by a local lock; different actions or repositories may run concurrently.

Version commands
----------------

``ptk version show/check/generate`` discovers versions and optionally writes an
ignored snapshot. There are no bump/set/tag commands. In VMR mode use
``ptk ALIAS version ...``. See :doc:`versioning` for sources and generators.

``ptk setup init`` requires a configuration directory supplied by the user.
Enter it at the terminal prompt or pass ``--config-dir PATH``; there is no
default. Scripts and ``--yes`` require the option. The path is relative to each
repository root. Root metadata stays minimal; initial
configuration fragments live in topic folders under PATH. ``actions/hello.ptk.yml``
and ``actions/build.ptk.yml`` provide separate runnable examples. Optional fields
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
