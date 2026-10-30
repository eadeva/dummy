Introduction and goals
======================

PTK provides a repository-defined CLI for recurring engineering work: building,
testing, generating files, preparing packages and collecting results. Teams
write jobs once and expose typed parameters and variant choices through the
terminal. CX pipelines invoke the same jobs while retaining their own orchestration.

The main stakeholders are developers executing jobs, maintainers authoring
configuration and plugins, and CX/release engineers preparing reproducible
artifacts. Assistant and editor integrations consume CLI-owned configuration
metadata; they do not define a separate loading model.

Quality priorities
------------------

* Predictability: conventional file ownership, explicit overrides and validated
  references make the effective configuration explainable.
* Usability: concise command groups, typed help and persistent shell completion
  make project commands discoverable.
* Isolation: jobs select their runtime and receive a deliberately composed
  environment rather than inheriting every caller setting.
* Diagnosability: source locations, step logs, canonical results and retained
  reports preserve the information needed to investigate failures.
* Maintainability: shared models and application use cases support several
  interfaces without duplicating execution rules.

The stakeholder baseline is in :doc:`/requirements/stakeholder`. Implementation
coverage and acceptance are separate: an existing behavior can still be under
review as a requirement. This architecture documents the CLI and its deployment
boundary, not the extension's internal design.
