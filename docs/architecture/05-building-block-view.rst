Building block view
===================

The code is organized by responsibility rather than by command alone.

.. list-table:: Principal building blocks
   :header-rows: 1
   :widths: 20 45 35

   * - Block
     - Responsibility
     - Main dependencies
   * - Drivers
     - Parse commands, route workspaces, present output and completion
     - Application services and interface adapters
   * - Application
     - Coordinate loading, preparation, execution, reports and maintenance
     - Domain rules and ports
   * - Domain
     - Typed data, validation, variant/expression rules, planning and canonical results
     - Python data structures and model libraries
   * - Adapters
     - Filesystem, YAML, processes, Git, environments, tools, secrets and report formats
     - Ports, domain data and external libraries/tools
   * - Composition root
     - Select and construct concrete implementations and built-ins
     - Application and adapters

The intended dependency direction keeps policy separate from effects. This is a
code organization rule, not a claim that an architectural dependency checker is
currently enforcing every import. Some CLI modules coordinate concrete adapters
for interface-specific operations.

Configuration and execution
---------------------------

``LoadProject`` uses ``FileConfigSource`` for discovery/loading and domain rules
for validation. Configuration schemas and ownership metadata come from the same
model. ``PrepareRun`` and ``RunJob`` coordinate selection, parameter resolution,
planning, environment/tool preparation and execution. Workflows schedule job
calls while preserving the owning repository's context.

Results and integrations
------------------------

The report service joins stored execution data with importer contributions.
Report exporters do not execute jobs. Plugin entry points extend steps,
reporters, report contributors, secret providers, installers and generators;
only explicitly selected installed distributions are loaded.

See :doc:`/reference/modules` for source paths and :doc:`/reference/plugins`
for callable contracts. Internal classes are not all stable public APIs.
