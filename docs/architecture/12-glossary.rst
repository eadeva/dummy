Glossary
========

.. glossary::

   Job
      A named, parameterized sequence of executable steps in one repository.

   Step
      A command, built-in handler or nested group within a job, with execution
      and reporting policy.

   Workflow
      Local orchestration of job calls, with explicit job dependencies and
      optional cross-repository routing in a VMR.

   Variant
      A concrete selection of feature values, components and associated data
      validated against the project's constraints.

   Component
      A registered repository-local source directory whose feature declarations
      live in ``component.variants.ptk.yml``.

   VMR
      Virtual monorepo: a workspace routing commands to independently configured
      repositories. It does not merge their configuration models.

   Marker
      The ``.main.ptk.yml`` file identifying a project or manual workspace.

   Provenance
      The source file and location associated with an assembled configuration
      value.

   Canonical report
      PTK's format-independent representation of execution and imported results.

   Importer / contributor
      A reader that converts tool output or captured logs into report data.

   Exporter / reporter
      A renderer that writes a canonical report in a selected output format.

   Disposition
      Whether a log finding is active, ignored or justified, independently of
      its original warning/error severity.

   Maintainer
      A user admitted by project identity rules to maintenance command namespaces.
      This controls CLI availability; it is not an operating-system privilege.

   Self-service
      Commands that configure the current user's PTK environment, tools,
      credentials, completion, hooks or editor integration.

   QM
      The selected safety-classification value for this requirements set.
      It is not a lifecycle status or verification result.

   Requirement lifecycle status
      Review/acceptance state, separate from whether behavior exists in code.
