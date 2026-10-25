Authoring skills
================

Repository-local assistant instructions live in ``.claude/skills``. They describe
the implemented CLI and point to source files and verification commands.
Paths inside a skill are relative to the repository root.

ptk-config-authoring
--------------------

.. literalinclude:: ../.claude/skills/ptk-config-authoring/SKILL.md
   :language: markdown

ptk-action-authoring
--------------------

.. literalinclude:: ../.claude/skills/ptk-action-authoring/SKILL.md
   :language: markdown

ptk-python-steps
----------------

.. literalinclude:: ../.claude/skills/ptk-python-steps/SKILL.md
   :language: markdown

ptk-variant-model
-----------------

.. literalinclude:: ../.claude/skills/ptk-variant-model/SKILL.md
   :language: markdown

ptk-credentials
---------------

.. literalinclude:: ../.claude/skills/ptk-credentials/SKILL.md
   :language: markdown

ptk-shared-configs
------------------

.. literalinclude:: ../.claude/skills/ptk-shared-configs/SKILL.md
   :language: markdown

ptk-tools-setup
---------------

.. literalinclude:: ../.claude/skills/ptk-tools-setup/SKILL.md
   :language: markdown

ptk-reporting
-------------

.. literalinclude:: ../.claude/skills/ptk-reporting/SKILL.md
   :language: markdown

ptk-troubleshooting
-------------------

.. literalinclude:: ../.claude/skills/ptk-troubleshooting/SKILL.md
   :language: markdown

ptk-development
---------------

.. literalinclude:: ../.claude/skills/ptk-development/SKILL.md
   :language: markdown

ptk-docs-writing
----------------

.. literalinclude:: ../.claude/skills/ptk-docs-writing/SKILL.md
   :language: markdown


Using these skills
------------------

These are repository-local instructions; installing the PTK wheel does not
install assistant skills. In a checkout, explicitly point your assistant to the
relevant ``.claude/skills/<name>/SKILL.md``. Paths in the skills assume the PTK
repository root. To reuse them elsewhere, retain access to the referenced PTK
source/docs/examples or adapt those references to a pinned checkout. Do not
assume every assistant discovers the ``.claude`` directory automatically.

Tests validate the catalog and references, execute the authoring starter and
load the plugin example through its declared distribution entry point.

ptk-vmr
-------

.. literalinclude:: ../.claude/skills/ptk-vmr/SKILL.md
   :language: markdown

ptk-plugin-development
----------------------

.. literalinclude:: ../.claude/skills/ptk-plugin-development/SKILL.md
   :language: markdown
