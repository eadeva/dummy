Authoring configuration
=======================

Files and precedence
--------------------

Start with ``main.ptk.yml``. Put reusable fragments in ``*.ptk.yml`` and load
them with ``include: [ptk/actions/*.ptk.yml]``. Includes are merged in order.
The loader then applies ``ci.ptk.yml`` when CI is enabled, ``local.ptk.yml``,
and command-line ``--set PATH=VALUE`` overrides. Keep local overrides out of git.
Use global ``--no-ci`` to inspect local behavior independently of the host.

Mappings merge deeply; lists replace. ``!replace`` replaces a node,
``!append`` extends a list, and ``!include`` inserts another file. Paths in
includes are relative to the including file. Unknown fields fail validation;
``ptk config show --sources`` identifies their source files and lines.

A ``variants`` string names a separate variant file. Other schema fields use
the types in :doc:`reference`. ``ptk_version`` is a version requirement; this
repository's development version needs a range such as ``>=0.1.0.dev0,<0.2``.

Actions and parameters
----------------------

Action names use lowercase letters, digits and hyphens, starting with a letter.
Parameters use lowercase letters, digits and underscores. Built-in command and
option names are reserved. An action needs at least one step. The default action
must exist and be available to ordinary users.

Parameters become CLI options: ``build_type`` becomes ``--build-type``;
boolean options get positive and negative forms. Precedence is explicit CLI
value, parameter file, declared environment variable, then default.
A required parameter cannot also have a default. Choice parameters need choices.
Defaults may refer to variables, environment or variant data, but not other
parameters. Validate them for each concrete variant you support.

Steps and execution
-------------------

Steps are an ordered list of single-key mappings, for example::

   actions:
     build:
       steps:
         - check:
             run: [check.py]
             python: {interpreter: cli}

Each step has exactly one of ``run``, ``uses`` or nested ``steps``.
Names must be unique within their set. ``parallel`` applies only to sets;
``python`` and ``passthrough`` apply to command steps; ``with`` applies to
``uses``. Prefer argument lists for paths containing spaces and user-supplied
parameters. String commands use platform shell syntax.

The registered built-ins are ``echo``, ``wait`` and ``report.import``.
``configs sync`` and ``setup`` are CLI commands; equivalent ``uses`` handlers
from the plan are not registered yet. Read the active code before adding new
built-in names. ``--from`` and ``--to`` select top-level steps.

Python modes are mutually exclusive: ``uvx`` for a Python tool, ``venv`` for
cached requirements/packages, ``project`` for a uv project, or
``interpreter: cli`` for ptk's interpreter. Pin tool versions in reproducible
project configurations. Dry runs describe runtimes without creating them.

Substitution and conditions
---------------------------

Use ``${vars.name}``, ``${params.name}``, ``${env:NAME}``,
``${env:NAME:-fallback}``, ``${project.root}``, ``${vh.variant}``,
``${vh.features.FEATURE}``, ``${vh.data.name}``, and run paths such as
``${run.build_dir}``. Escape literal substitutions with ``$${...}``.
Unknown references are errors. The run paths are per step where applicable.

``when`` uses the safe expression evaluator, not Python execution. Feature names,
``COMPONENT_*`` flags, ``variant``, ``os``, ``ci`` and supported namespaces can
be used. Check the resolved values with ``variant show`` and ``variant explain``.
Variants can inherit through ``extends``, carry aliases and free-form ``data``,
and mark common parents ``abstract: true``.

Credentials
-----------

Declare credential fields and provider order under ``credentials``. The default
chain is env, keyring, gopass, vault, prompt. Keyring is optional; prompting is
unavailable in CI. Supply secrets to individual steps using::

   secrets: {TOKEN: service.token}

Never interpolate secrets into command arguments, URLs or shared config files.
A shell command that expands a secret environment variable into an argument
still exposes that secret in the child's command line. Have the child program
read its environment directly. Use ``creds setup``, ``creds list``, and
``creds set NAME FIELD`` to diagnose or provision values. Do not include real
credentials in examples, fixtures or documentation.

Tools, configs and outputs
--------------------------

Declare tool version checks under ``tools`` and reference them in an action's
``requires_tools``. Missing tools block real execution. Preview installation
with ``setup --dry-run``. System package managers require ``--allow-system``;
Chocolatey bootstrap is explicit. Prefer checksummed downloads.

Only entries under ``configs`` are managed. Preview ``configs sync --diff``;
commit generated files and enforce ``configs check`` in CI. Ruff uses a generated
``ruff-base.toml`` and a project-owned ``ruff.toml`` extending it.

The layout defaults to ``_builds``, ``_bin``, ``_logs`` and ``_reports``.
Write test results into ``PTK_STEP_REPORTS_DIR``. JUnit, SARIF and Cobertura
are imported into configured JSON, HTML, JUnit, Markdown or GitHub reports.
``report export`` regenerates reports from stored runs. Use log files and
``events.jsonl`` when diagnosing failed or skipped steps.

Maintainer visibility and current limits
----------------------------------------

``maintainers.ptk.yml`` lists git email and/or OS username. An action with
``audience: maintainer`` is hidden from other users, including generated help
and VS Code tasks. This is a convenience feature, not a security boundary.

``init``, ``variant set/new/gui``, migration, background steps, variant generators
and plugin entry-point discovery remain planned. Do not rely on roadmap examples
for these features. Use the commands shown by ``ptk --help`` and the runnable
quickstart as the supported starting point.
