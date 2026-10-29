Source module map
=================

This map identifies implementation entry points without importing modules to
produce an API dump. The public integration contracts are documented in
:doc:`plugins` and :doc:`/guides/editor`; internal module names are not a
compatibility promise.

.. list-table:: Main responsibilities
   :header-rows: 1
   :widths: 35 65

   * - Source path
     - Responsibility
   * - ``src/ptk/drivers/cli``
     - Click command construction, completion, workspace routing and terminal output.
   * - ``src/ptk/application/use_cases``
     - Project loading, preparation, execution, workflows, reports and maintenance operations.
   * - ``src/ptk/application/ports.py``
     - Interfaces for host, configuration, processes, secrets, tools and external services.
   * - ``src/ptk/domain/config``
     - Pydantic models, validation rules, fixed document layout, substitution and template metadata.
   * - ``src/ptk/domain/execution``
     - Execution plans, parameter conversion, environment composition and step models.
   * - ``src/ptk/domain/variants``
     - Feature and component models, constraints and build-system generators.
   * - ``src/ptk/domain/reporting``
     - Canonical report data, summaries and diagnostic policies.
   * - ``src/ptk/adapters/config``
     - Filesystem discovery and YAML loading with source locations.
   * - ``src/ptk/adapters/process.py``
     - Portable subprocess execution and cancellation.
   * - ``src/ptk/adapters/reporting``
     - Result importers, log analysis, history storage and exporters.
   * - ``src/ptk/adapters/credentials``
     - Environment, vault, keyring, prompt and gopass providers.
   * - ``src/ptk/bootstrap.py``
     - Construction of concrete services and built-in registrations.
   * - ``src/ptk/authoring_bundle.py`` and ``extension_bundle.py``
     - Allowlisted documentation, skills, examples and packaged editor artifact.

Dependency responsibilities and runtime interactions are described in
:doc:`/architecture/05-building-block-view` and
:doc:`/architecture/06-runtime-view`.
