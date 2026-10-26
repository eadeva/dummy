Authoring configuration
=======================

Files and precedence
--------------------

Place a project's ``.main.ptk.yml`` at the repository root. It must declare an alias and
configuration directory, for example::

   repository:
     alias: firmware
     config_path: tooling/ptk
   project:
     name: Firmware
   include: [actions.ptk.yml]

The alias uses lowercase letters, digits and hyphens, starting with a letter.
``config_path`` is a relative, existing directory inside the repository; ``.``
keeps configuration alongside the entry file. Entry-file includes (including
``!include`` and ``variants:``) resolve from this directory. Includes inside
fragments remain relative to the fragment itself.

Automatic ``versioning.ptk.yml``, ``tools.ptk.yml``, ``<action>.tools.ptk.yml``, ``cx.ptk.yml``,
``local.ptk.yml`` and ``maintainers.ptk.yml`` are discovered in that directory.
The loader applies shared tool files, main/includes, CX when enabled, local,
and finally CLI ``--set`` overrides. Repository metadata cannot be overridden.
Keep local overrides out of git. ``variant set/new`` writes the local overlay
in this configuration directory. Commands, workspace outputs and shared tool
configuration outputs still use the repository root.

Automatic discovery searches upwards and stops at a Git repository boundary.
The old ``main.ptk.yml`` filename is not discovered. ``--config`` explicitly
selects an entry file, including standalone exported snapshots.
Use global ``--no-ci`` to inspect local behavior independently of the host.

A manual VMR has a separate workspace-root ``.main.ptk.yml`` with
``virtual_monorepo: true`` and an optional ``members: [nested/repository, other]``
list of exact relative paths. This marker has no ``repository``, includes or
project settings. Without ``members``, ptk checks direct child directories only;
each participating project still declares its own alias and configuration path.
Git-repo workspaces instead use ``.repo/project.list`` and need no PTK marker.

In a project entry file, omit ``virtual_monorepo`` for automatic detection or
set it to ``false`` to remain standalone and opt out of workspace listings.
The field requires a YAML boolean, and cannot be supplied by fragments, overlays
or ``--set``. Repository metadata and workspace markers must be literal YAML,
without include tags or merge directives. See :doc:`cli` for membership rules
and how commands behave from workspace roots and member directories.

Mappings merge deeply; lists replace. ``!replace`` replaces a node,
``!append`` extends a list, and ``!include`` inserts another file. Unknown
fields fail validation; ``ptk setup config show --sources`` identifies their
source files and lines.

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

The registered built-ins are ``echo``, ``wait``, ``report.import``,
``configs.sync``, ``tools.ensure``, ``files.copy``, ``files.clean`` and
``variant.generate`` and ``version.generate``. Their contracts are in :doc:`plugins`.
``--from`` and ``--to`` select top-level steps.

Python modes are mutually exclusive: ``uvx`` for a Python tool, ``venv`` for
cached requirements/packages, ``project`` for a uv project, or
``interpreter: cli`` for ptk's interpreter. Pin tool versions in reproducible
project configurations. ``python: {project: ., groups: [docs]}`` adds dependency
groups from that project's ``pyproject.toml`` to the uv run. ``groups`` is only
valid with ``project`` mode; the normal uv default groups still apply.
Dry runs describe runtimes without creating them.

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

Report summaries
----------------

HTML reports start with the recorded PTK/project versions, repository alias,
selected variant description, inheritance, active components and feature values.
Declared tool dependencies show detected versions and their resolved check
executable paths in the command environment. Unknown versions/sources are labeled
explicitly; configured download URLs are not presented as proven installation
sources. This is a snapshot of declared tools, not a transitive Python package inventory.
Multiple tool versions/sources observed during a run are retained.

This context is saved with the run, so exporting an older report does not replace
its versions or variant settings with the current configuration. Older runs without
this data show "Not recorded". JSON, Markdown/GitHub summaries and JUnit properties
also carry recorded context.

The Tests section and each test suite have summary cards for executed, passed,
skipped and failed cases. Executed excludes skipped cases; failed includes both
assertion failures and test errors (for example, fixture/setup errors). Detailed
case rows retain the distinction between failures and errors. Step counts remain
separate from test-case counts.

Every HTML table has a case-insensitive substring filter for each column. Filters
combine across columns, operate locally/offline, and show the remaining row count.
Clear a filter to restore rows. Filtering does not change recorded totals or cards.

Maintainer visibility and current limits
----------------------------------------

``maintainers.ptk.yml`` lists git email and/or OS username. An action with
``audience: maintainer`` is hidden from other users, including generated help
and VS Code tasks. This is a convenience feature, not a security boundary.

Variant editing, matrix runs and legacy CLI aliases are described in :doc:`cli`.
The installed plugin interfaces, generators and built-in command visibility are
covered in :doc:`plugins`. Background process and desktop GUI limitations are in :doc:`m11`.


Additional execution controls
-----------------------------

``path`` parameters accept paths containing spaces. ``secret`` parameters use
``env:`` or a hidden prompt requested with ``--PARAM`` (without a value).
They have no literal defaults, are masked in run metadata, are not exported as
``PTK_PARAM_*``, and may be substituted only in step ``env``. Prefer credential
providers for reusable credentials. Never pass secret values as CLI arguments.

``report: false`` excludes a step and its descendants from exported reports and
tool-result imports; audit logs and the overall failure status remain complete.
Groups and built-ins support retries and deadlines. A group deadline cancels its
children, without cancelling unrelated groups. Repeating a group repeats all of
its children, so enable retries only for repeatable work. Built-in/plugin Python
handlers must cooperate with ``ctx.cancel.is_set()``; Python threads cannot safely
be forcibly terminated. ``wait`` cooperates with deadlines and Ctrl+C.

Shared defaults and tool files
------------------------------

``tools.ptk.yml`` and ``<action>.tools.ptk.yml`` in the configuration directory are loaded
automatically when present. Action filenames are discovered for actions declared
in the main configuration, its includes, global tools file or enabled overlays.
Files already included explicitly are not applied again automatically.

Precedence, from lowest to highest: automatic ``tools.ptk.yml`` and ``versioning.ptk.yml``, automatic action
tool files (alphabetical), main configuration/includes, ``cx.ptk.yml`` in CI,
``local.ptk.yml``, then command-line overrides. Explicit includes retain their
normal position. Additional tool definitions in action files are shared definitions;
put action-specific changes under that action's ``requires_tools``.

``cx.ptk.yml`` is the automatic workflow overlay filename. GitHub Actions is
recognized automatically; ``--ci`` / ``--no-ci`` can force the mode. The old
``ci.ptk.yml`` filename is not automatically loaded.

Global ``param_defaults`` supplies defaults only to parameters that an action
explicitly declares. Action-specific ``default`` values take precedence. An
explicit ``default: null`` opts out; ``required: true`` parameters remain required.
Inherited values are validated against each parameter's type/choices, and
``config show --sources`` retains the global value's source location::

   param_defaults:
     jobs: 8
   actions:
     build:
       params:
         jobs: {type: int}
       steps:
         - compile: {run: [cmake, --build, build, -j, "${params.jobs}"]}

Tool requirements merge **per tool**, not by replacing the entire list::

   # tools.ptk.yml
   tools:
     git: {check: git --version}
     cmake: {version: ">=3.28", check: cmake --version, choco: cmake}
     ninja: {check: ninja --version}
   requires_tools: [git, cmake]

   # build.tools.ptk.yml
   actions:
     build:
       requires_tools:
         cmake: {version: ">=3.30"}
         ninja: true

``build`` requires git, cmake and ninja, with its own CMake version constraint.
Other actions retain the global requirements and CMake definition. Use
``git: false`` to disable only git for one action. ``requires_tools: []`` or ``{}``
changes nothing; an action's unmentioned global requirements remain inherited.
List shorthand enables/adds named tools; mappings can enable, disable or override
a named tool's settings. All referenced names must be declared under ``tools``.

``setup install --action build`` uses that action's effective tool settings.
Selecting actions that require conflicting settings for the same tool fails
before installation; install for those actions separately. Without ``--action``,
``setup install`` uses global requirements when supplied, otherwise all declared
tools. Declaring a tool alone does not make it a requirement of every action.

Isolated action environments
----------------------------

``environment.isolate`` defaults to true. Each action receives a new environment
containing OS essentials, explicitly kept variables, configured values and its
selected managed tools. ``inherit_path`` defaults to false: PATH starts with
standard OS directories, not the caller's potentially repository-specific PATH.
This is environment isolation, not a filesystem or process sandbox::

   environment:
     isolate: true
     inherit_path: false
     keep: [HTTP_PROXY, HTTPS_PROXY]
     set: {BUILD_MODE: reproducible}
   actions:
     build:
       environment:
         keep: [HTTP_PROXY, HTTPS_PROXY, COMPANY_SDK]
       steps:
         - compile: {run: [compiler, source.c]}

An action's explicitly set environment fields override the global fields.
Lists replace, so include all desired ``keep`` entries in an action override.
``isolate: false`` deliberately inherits ordinary host variables;
``inherit_path: true`` separately opts into caller PATH. Step ``env`` and secrets
are applied to that command only. Neither the host process nor another action's
environment is mutated. Tool versions are rechecked in the final subprocess
environment, including Python-runtime and step overrides.

Managed downloads and Python tools are stored by tool name and effective
version/source identity. Only installations selected by the action's effective
requirements (or its explicit ``tools.ensure`` selections) enter its PATH.
A later ``tool: true`` keeps earlier settings; ``tool: false`` disables that
requirement. System binaries on the OS path are version-checked. Chocolatey,
apt/dnf and custom plugin installers are shared host operations and cannot
provide the same side-by-side isolation. Prefer managed downloads or Python
tools for incompatible repository versions. Host PATH entries pointing into
PTK's managed cache are removed before the selected installations are added.

The complete ``examples/authoring`` starter is exercised by the skill tests.

Version discovery is documented in :doc:`versioning`. It uses a maintained
``versioning.ptk.yml`` and ignored per-run ``.gen.version.ptk.yml`` snapshots.
