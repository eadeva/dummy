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

   uv run ptk -c examples/quickstart/main.ptk.yml setup config validate
   uv run ptk -c examples/quickstart/main.ptk.yml setup install --action build --dry-run
   uv run ptk -c examples/quickstart/main.ptk.yml setup creds list

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
