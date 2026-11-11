Authoring skills
================

Canonical assistant instructions live in ``.github/skills`` and
``.github/agents`` so that editors discover them in PTk's own checkout. Sixteen
project-facing skills use links relative to their SKILL.md files and are bundled
with the wheel. Two maintainer skills operate on PTk's own source checkout.
Do not run ``ptk maintainer sync agent`` in PTk's checkout: the canonical sources
already occupy the managed paths, so synchronization only reports conflicts.

ptk-config-authoring
--------------------

.. literalinclude:: ../../.github/skills/ptk-config-authoring/SKILL.md
   :language: markdown

ptk-job-authoring
--------------------

.. literalinclude:: ../../.github/skills/ptk-job-authoring/SKILL.md
   :language: markdown

ptk-python-steps
----------------

.. literalinclude:: ../../.github/skills/ptk-python-steps/SKILL.md
   :language: markdown

ptk-variant-model
-----------------

.. literalinclude:: ../../.github/skills/ptk-variant-model/SKILL.md
   :language: markdown

ptk-credentials
---------------

.. literalinclude:: ../../.github/skills/ptk-credentials/SKILL.md
   :language: markdown

ptk-shared-configs
------------------

.. literalinclude:: ../../.github/skills/ptk-shared-configs/SKILL.md
   :language: markdown

ptk-tools-setup
---------------

.. literalinclude:: ../../.github/skills/ptk-tools-setup/SKILL.md
   :language: markdown

ptk-reporting
-------------

.. literalinclude:: ../../.github/skills/ptk-reporting/SKILL.md
   :language: markdown

ptk-troubleshooting
-------------------

.. literalinclude:: ../../.github/skills/ptk-troubleshooting/SKILL.md
   :language: markdown

ptk-development
---------------

.. literalinclude:: ../../.github/skills/ptk-development/SKILL.md
   :language: markdown

ptk-docs-writing
----------------

.. literalinclude:: ../../.github/skills/ptk-docs-writing/SKILL.md
   :language: markdown


Using these skills
------------------

Run ``ptk maintainer sync agent`` to install project-facing skills in a consuming
repository. It also installs the PTk expert custom agent at
``.github/agents/ptk-expert.agent.md``. The installer
copies skills into ``.github/skills`` and version-matched offline documentation,
examples and the schema into ``.github/ptk``. It rewrites relative links for that
layout; no PTk source checkout is required. See :doc:`/guides/editor` for update and check
behavior. Installing the wheel alone does not modify any consuming repository.

The development and docs-writing skills remain checkout-only. Point an assistant
working on PTk itself to those source skills explicitly.

Tests validate the catalog, agent/skill Markdown links and offline RST document,
include and download targets inside the installed bundle, execute the authoring starter and
build the ordinary Python tool example and run its CLI through uv.

ptk-vmr
-------

.. literalinclude:: ../../.github/skills/ptk-vmr/SKILL.md
   :language: markdown

ptk-workflow-authoring
----------------------

.. literalinclude:: ../../.github/skills/ptk-workflow-authoring/SKILL.md
   :language: markdown

ptk-versioning
---------------

.. literalinclude:: ../../.github/skills/ptk-versioning/SKILL.md
   :language: markdown

ptk-package-preparation
-----------------------

.. literalinclude:: ../../.github/skills/ptk-package-preparation/SKILL.md
   :language: markdown

ptk-log-analyzer
----------------

.. literalinclude:: ../../.github/skills/ptk-log-analyzer/SKILL.md
   :language: markdown

ptk-expert agent
----------------

.. literalinclude:: ../../.github/agents/ptk-expert.md
   :language: markdown

Project independence and agent selection
----------------------------------------

All project-facing skills share :doc:`/guides/agent-guide`. They discover the selected
runtime, schema, file ownership, execution routes and run evidence instead of
assuming example configuration. They can diagnose supplied artifacts when PTk is
unavailable, but must state which runtime validation could not be performed.
PTk core development and documentation-writing skills remain checkout-only.

Keep one ``ptk-expert`` agent and load focused skills on demand. A separate
read-only reviewer can be useful for independent validation of substantial
changes; parallel readers can help with unrelated repositories or logs. Neither
is required, and links do not automatically launch agents. Keep one edit owner
and final verifier. This avoids duplicating PTk rules across specialist agents.

ptk-github-workflows
--------------------

.. literalinclude:: ../../.github/skills/ptk-github-workflows/SKILL.md
   :language: markdown

The local workflow skill authors the PTk graph; the GitHub skill generates and
reviews callable native pipelines, matrix setup, Docker/VMR checkout TODOs and
artifact Actions. It includes output declarations and never assumes a consumer
project has PTk's own verify jobs or packaging scripts. Synchronization includes
the matching GitHub, matrix, output-reuse and reporting reference guides.

Keep project instructions separate
----------------------------------

The installed bundle is version-matched reference material, not a copy of PTk's
source project. A consumer can have different job names, no variants, no Python
package and any valid configuration directory. Start with the runtime discovery
contract in :doc:`agent-guide` and the local onboarding flow in :doc:`local-setup`.

Keep team-specific assistant instructions in files owned by that project. Do not
edit the installed reference examples to configure builds, and do not modify the
bundle manifest to hide drift. Synchronization reports conflicting edits and
preserves them. Reconcile changes intentionally before updating the bundle, or
use ``ptk maintainer sync agent --force`` to review the listed files and confirm
their replacement.

A successful link check proves resource availability; it does not prove that an
AI assistant or the VS Code UI will behave correctly in every environment.
Installed-wheel tests and disposable consumer scenarios provide additional
execution evidence. Browser/native-Windows acceptance is reported separately.

ptk-devops
----------

.. literalinclude:: ../../.github/skills/ptk-devops/SKILL.md
   :language: markdown

Use this skill for cross-cutting project maintenance: local onboarding, Docker
readiness, shared policy and artifact/CX delivery. It selects focused skills for
implementation and keeps one expert agent responsible for the result. A second
maintainer agent is unnecessary: maintenance is a task scope, not a permission
grant or a different project model.
