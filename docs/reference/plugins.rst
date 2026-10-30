Plugin and generator configuration
==================================

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

Use the installed plugin's documented names in configuration:

.. list-table:: Plugin configuration
   :header-rows: 1
   :widths: 30 70

   * - Capability
     - Configuration
   * - Step
     - Set a job step's ``uses`` to the registered name and pass options in ``with``.
   * - Report exporter
     - Add the registered format name to ``report_formats`` or select it with ``ptk report export JOB -f NAME``.
   * - Result importer
     - Select the plugin distribution in ``plugins``; its importer reads results from visible steps.
   * - Credential provider
     - Add the provider name to ``credentials.NAME.providers`` and select it with ``--store`` when saving a value.
   * - Tool installer
     - Set ``tools.NAME.installers.PLUGIN: {options...}``. Configure the environment/PATH so PTK can find the installed executable.
   * - Variant generator
     - Add the registered name to the ``generators`` list of any job step.

The plugin supplies its accepted option names and supported PTK versions.
For example, after installing a distribution that provides ``company.check``::

   steps:
     checks:
       uses: company.check
       with:
         mode: strict

Here ``mode`` is an example plugin option, not a built-in PTK field.

Variant generators
------------------

Select built-in or enabled plugin generators directly on a step::

   steps:
     configure:
       generators: [cmake, header]
       run: [cmake, -S, ., -B, "${run.build_dir}/cmake", "-DPTK_VARIANT_FILE=${run.build_dir}/variant.cmake"]

A step may instead contain only ``generators``. Generation requires a valid
concrete variant and precedes every command/plugin attempt. The eight built-ins
are ``header``, ``cmake``, ``bazel``, ``gn``, ``make``, ``yocto``, ``robot`` and
``sphinx``. Outputs always belong to the step's build directory. The former
``uses: variant.generate`` interface and its output override are removed.

See :doc:`/guides/variant-generation` for the data contract, escaping restrictions,
project responsibilities, native build integration and downloadable Bazel helper.
A generator plugin receives its own copy of the prepared ``ResolvedVariant`` and
returns a dictionary of relative filenames to UTF-8 strings. Feature keys in
``variant.values`` are component-qualified. Do not mutate external state in a
generator. PTK validates all returned names/content before writing, rejects
colliding names and directory/file conflicts, and replaces each file atomically.
Plugins execute as trusted Python; they are responsible for their own side effects
and bounded runtime. There is no transaction across files or plugin functions.

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

Version generators
------------------

The bundled ``version.generate`` step supports C headers, CMake, MSBuild, Python
and JSON. See :doc:`/guides/versioning` for source selection, output configuration
and examples.
