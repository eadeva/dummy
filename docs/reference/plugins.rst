Plugins, generators and additional built-ins
============================================

Loading installed plugins
-------------------------

Install your extension in the same Python environment as PTK and list its
**distribution name** in the project. Discovery does not install anything::

   # config/ptk/project.ptk.yml
   plugins:
   - company-ptk-extension

Only selected distributions are imported. Missing packages/entry points,
non-callable handlers and duplicate or reserved names are errors. Plugins run
as trusted Python code with the user's permissions; the allow-list is not a
sandbox. Ordinary projects with no ``plugins`` do not load these extensions.

Register callables in the extension's ``pyproject.toml``::

   [project.entry-points."ptk.steps"]
   "company.check" = "company_extension:check"

   [project.entry-points."ptk.generators"]
   custom = "company_extension:generate"

The supported contracts are:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Entry-point group
     - Callable contract
   * - ``ptk.steps``
     - ``(step: PlannedStep, out, ctx: BuiltinContext) -> int``. Return an exit code;
       write messages with ``out`` for masking. Poll ``ctx.cancel.is_set()``.
   * - ``ptk.reporters``
     - ``(report: Report, target: Path) -> Path``. Write the chosen format and return
       its file. Select its entry-point name in ``report_formats`` or ``-f``.
   * - ``ptk.report_contributors``
     - ``(reports_dir: Path, labels: list[str]) -> list[Contribution]``. Read results
       only for the supplied visible step labels; disabled steps are filtered out.
   * - ``ptk.secret_providers``
     - ``() -> SecretProvider``. Implement the port in ``application/ports.py``;
       use the entry-point name in ``credentials.NAME.providers`` and ``--store``.
   * - ``ptk.installers``
     - ``(tool_name: str, options: dict, out) -> None``. Raise ``PtkError`` on failure.
       Configure ``tools.NAME.installers.PLUGIN: {options...}``. Plugin methods
       precede platform methods; PTK rechecks the configured version afterward.
       Make executables discoverable by the configured environment/PATH.
   * - ``ptk.generators``
     - ``(variant: ResolvedVariant) -> dict[str, str]``. Return relative filenames
       and text; PTK validates destinations and writes below the output folder.

Handlers can raise ``PtkError`` with actionable messages. Built-in step retries
may call handlers again: make them repeatable or leave retries disabled. Python
handlers must cooperate with cancellation; only subprocesses support forced
process-tree termination. Do not print secrets directly or include them in files.

Variant generators
------------------

Seven built-in generators implement the same contract as external generators::

   - generate:
       uses: variant.generate
       with:
         generators: [header, cmake, bazel, make, yocto, robot, sphinx]
         output: _bin/generated

Omit ``output`` to use the step's build folder. A concrete valid variant is
required. Outputs are ``variant.h``, ``variant.cmake``, ``variant.bzl``,
``variant.mk``, ``variant.inc``, ``variant.robot`` and ``variant.rst``.
Regeneration replaces these generated files; do not edit them manually.
Names use ``VH_FEATURE``, ``VH_COMPONENT_NAME`` and ``VH_VARIANT``. Booleans become
0/1 except in Bazel's native dictionary. Inactive values are empty (or omitted
macros in C). These exports contain feature/component values, not arbitrary
variant ``data``; custom generators may consume that data.

Generators escape their language's strings. Make rejects newlines, backslashes
and surrounding whitespace; Yocto rejects newlines and variable expansions.
These values fail explicitly rather than generating ambiguous build syntax.
Filenames must stay beneath the selected project-local output directory, and
collisions between generators are rejected before writing.

Additional built-ins
--------------------

* ``configs.sync`` accepts optional ``with: {names: [ruff, clang-format]}`` and
  runs the same shared-config service as ``ptk maintainer sync configs``.
* ``tools.ensure`` accepts ``with: {tools: [cmake], allow_system: false}``. All
  names must be declared. Place it before dependent commands. Jobs containing
  this step defer the initial required-tool check to the step; subsequent commands
  refresh the installed-tools PATH. Skipped/conditional ensure steps do not install.
* ``files.copy`` accepts ``files`` globs, ``to``, ``optional`` and ``overwrite``.
  Files are flattened into the destination. Duplicate basenames are errors, and
  existing files require explicit ``overwrite: true``. Destinations stay inside
  the project; the default is the step build folder.
* ``files.clean`` accepts explicit ``paths``. It only removes descendants of the
  configured build/bin/log/report folders; it refuses workspace roots and paths
  outside them. Do not remove the logs of the active run.

Built-in command visibility
---------------------------

Use canonical dotted paths, for example::

   # config/ptk/project.ptk.yml
   command_audience:
     self-service.creds: maintainer
     self-service.tools: maintainer
     report: all

Supported keys are ``self-service`` and its project operations (``tools``,
``creds``, ``doctor``, ``hooks``), individual ``self-service.hooks.install``,
``self-service.hooks.uninstall`` and ``self-service.hooks.status`` paths,
``pre-commit``, ``variant``, ``report`` and ``workflow``. The schema also accepts
``maintainer`` and its ``config``, ``sync``, ``version`` and ``artifacts`` paths;
these always require a listed maintainer, even when their policy is ``all``.
Restrictions apply to descendants, normal/HTML help and completion. ``init``,
``validate``, completion and extension installation remain available to all users.
There are no compatibility aliases. See :doc:`/guides/configuration` for the command
list and login-ID-only maintainer schema. This is not an operating-system
security boundary.

Runnable extension starter
---------------------------

``examples/plugin`` is a complete minimal distribution. Install it into the
Python environment that contains PTK, for example from a development checkout::

   uv pip install ./examples/plugin

Select ``plugins: [ptk-example-extension]`` and a step with
``uses: example.check``. The skill tests load the declared entry point and run
a real configured job. See the ``ptk-plugin-development`` authoring skill.

Credential-provider keys include ``storage_ref`` as well as logical ``ref``.
Persist by ``storage_ref`` to honor VMR namespaces. Provider availability checks
must be non-interactive; listing never calls ``get`` on persistent stores.
Custom installers must manage their own version-specific destinations and
configure a discoverable PATH explicitly; PTK cannot isolate arbitrary external
installer side effects.

Version generators
------------------

The bundled ``version.generate`` step supports C headers, CMake, MSBuild, Python
and JSON. See :doc:`/guides/versioning`. Custom ``ptk.steps`` handlers receive the resolved
run snapshot in ``ctx.versions``; consume that snapshot instead of rediscovering
Git state during execution. Existing variant generator contracts are unchanged.
