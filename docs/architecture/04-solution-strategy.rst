Solution strategy
=================

PTK separates a validated model from effects. Configuration adapters discover
owned files and attach locations; application loading assembles and validates
the model. Domain rules resolve variants, parameter values, substitutions and
execution plans. Concrete adapters perform filesystem, process and service I/O.

Dynamic Click commands expose configured jobs and workflows directly. Command
visibility follows namespace and maintainer rules. The same parameter metadata
supplies help, completion and machine-readable descriptions. Built-in commands
remain usable for diagnostics when a project cannot be loaded.

A prepared run fixes the selected variant, parameters, paths and relevant policy
before execution. Git values are read lazily and cached within the operation;
date values share the invocation's captured instant. Independent job variants
can run concurrently, while locks prevent simultaneous writes to the same
job/variant output history.

Report adapters import execution records and supported tool formats into a
canonical model, then exporters render that model. Log diagnostics retain both
severity and disposition, keeping suppression decisions separate from process
and test failures. Stored run inputs support later exports without silently
reinterpreting past results using today's configuration.

PTK exports schema and inventory from the same models and loader used by the
CLI. Packaged authoring resources follow the installed version. This minimizes
duplicate rules in integrations, although an incompatible CLI protocol change
still needs coordinated client work. See :doc:`/guides/editor`.
