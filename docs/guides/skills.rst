Authoring skills
================

Canonical assistant instructions live in ``.claude/skills``. Fifteen project-facing
skills use links relative to their SKILL.md files and are bundled with the wheel.
Two maintainer skills operate on PTK's own source checkout.

ptk-config-authoring
--------------------

.. literalinclude:: ../../.claude/skills/ptk-config-authoring/SKILL.md
   :language: markdown

ptk-job-authoring
--------------------

.. literalinclude:: ../../.claude/skills/ptk-job-authoring/SKILL.md
   :language: markdown

ptk-python-steps
----------------

.. literalinclude:: ../../.claude/skills/ptk-python-steps/SKILL.md
   :language: markdown

ptk-variant-model
-----------------

.. literalinclude:: ../../.claude/skills/ptk-variant-model/SKILL.md
   :language: markdown

ptk-credentials
---------------

.. literalinclude:: ../../.claude/skills/ptk-credentials/SKILL.md
   :language: markdown

ptk-shared-configs
------------------

.. literalinclude:: ../../.claude/skills/ptk-shared-configs/SKILL.md
   :language: markdown

ptk-tools-setup
---------------

.. literalinclude:: ../../.claude/skills/ptk-tools-setup/SKILL.md
   :language: markdown

ptk-reporting
-------------

.. literalinclude:: ../../.claude/skills/ptk-reporting/SKILL.md
   :language: markdown

ptk-troubleshooting
-------------------

.. literalinclude:: ../../.claude/skills/ptk-troubleshooting/SKILL.md
   :language: markdown

ptk-development
---------------

.. literalinclude:: ../../.claude/skills/ptk-development/SKILL.md
   :language: markdown

ptk-docs-writing
----------------

.. literalinclude:: ../../.claude/skills/ptk-docs-writing/SKILL.md
   :language: markdown


Using these skills
------------------

Run ``ptk maintainer sync agent`` to install project-facing skills in a consuming
repository. It also installs the PTK expert custom agent at
``.github/agents/ptk-expert.agent.md``. The installer
copies skills into ``.github/skills`` and version-matched offline documentation,
examples and the schema into ``.github/ptk``. It rewrites relative links for that
layout; no PTK source checkout is required. See :doc:`/guides/editor` for update and check
behavior. Installing the wheel alone does not modify any consuming repository.

The development and docs-writing skills remain checkout-only. Point an assistant
working on PTK itself to those source skills explicitly.

Tests validate the catalog and references, execute the authoring starter and
build the ordinary Python tool example and run its CLI through uv.

ptk-vmr
-------

.. literalinclude:: ../../.claude/skills/ptk-vmr/SKILL.md
   :language: markdown

ptk-workflow-authoring
----------------------

.. literalinclude:: ../../.claude/skills/ptk-workflow-authoring/SKILL.md
   :language: markdown

ptk-versioning
---------------

.. literalinclude:: ../../.claude/skills/ptk-versioning/SKILL.md
   :language: markdown

ptk-package-preparation
-----------------------

.. literalinclude:: ../../.claude/skills/ptk-package-preparation/SKILL.md
   :language: markdown

ptk-log-analyzer
----------------

.. literalinclude:: ../../.claude/skills/ptk-log-analyzer/SKILL.md
   :language: markdown

ptk-expert agent
----------------

.. literalinclude:: ../../.claude/agents/ptk-expert.md
   :language: markdown

Project independence and agent selection
----------------------------------------

All project-facing skills share :doc:`/guides/agent-guide`. They discover the selected
runtime, schema, file ownership, execution routes and run evidence instead of
assuming example configuration. They can diagnose supplied artifacts when PTK is
unavailable, but must state which runtime validation could not be performed.
PTK core development and documentation-writing skills remain checkout-only.

Keep one ``ptk-expert`` agent and load focused skills on demand. A separate
read-only reviewer can be useful for independent validation of substantial
changes; parallel readers can help with unrelated repositories or logs. Neither
is required, and links do not automatically launch agents. Keep one edit owner
and final verifier. This avoids duplicating PTK rules across specialist agents.

ptk-github-workflows
--------------------

.. literalinclude:: ../../.claude/skills/ptk-github-workflows/SKILL.md
   :language: markdown

The local workflow skill authors the PTK graph; the GitHub skill generates and
reviews callable native pipelines, matrix setup, Docker/VMR checkout TODOs and
artifact Actions. It includes output declarations and never assumes a consumer
project has PTK's own verify jobs or packaging scripts. Synchronization includes
the matching GitHub, matrix, output-reuse and reporting reference guides.
