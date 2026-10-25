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
     - Create a runnable project without overwriting existing files
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
   * - ``ptk variant list|show|explain|check``
     - Inspect the product line
   * - ``ptk report open|export``
     - View and regenerate reports
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

``ptk setup migrate SOURCE [--output FILE] [--name NAME] [--dry-run]`` converts
supported legacy configurations; ``ptk migrate`` remains an alias.
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

A ``.repo`` directory in the current directory or an ancestor activates VMR
mode. A member's ``.git`` symlink or ``gitdir:`` file also identifies the VMR
when its target is inside that workspace's ``.repo`` directory. Ordinary Git
worktrees do not activate VMR mode merely because they have a ``.git`` file.

When present, ``.repo/project.list`` defines the member paths. Otherwise ptk
walks working-tree roots, skipping Git metadata and symlinked directory trees.
Only members with a root ``.main.ptk.yml`` participate. Duplicate aliases and
member paths outside the workspace fail discovery.

Commands are grouped under the configured repository alias::

   ptk --help
   ptk firmware --help
   ptk firmware build
   ptk firmware setup install
   ptk bootloader variant list
   ptk --set vars.mode=debug firmware build

The same grouping applies from a member's subdirectory. Each repository has
isolated configuration, tools, plugins, permissions and output directories.
``ptk firmware`` runs that repository's default action; bare ``ptk`` lists the
repositories. There is no implicit run across all repositories. Global options
precede the alias. ``ptk --config path/to/.main.ptk.yml build`` explicitly selects
standalone mode. Generated VS Code tasks in VMR mode include the repository alias.

Shared VMR commands
-------------------

Alongside repository aliases, the VMR root exposes ``repos``, ``help``,
``setup config show/validate/schema``, ``setup doctor``, ``setup creds``,
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
This applies even with explicit ``--config`` inside a VMR. Identical definitions
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
