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
     - Add the registered name to the ``generators`` list of a ``variant.generate`` step.

The plugin supplies its accepted option names and supported PTK versions.
For example, after installing a distribution that provides ``company.check``::

   # config/ptk/jobs/check.ptk.yml
   steps:
   - checks:
       uses: company.check
       with:
         mode: strict

Here ``mode`` is an example plugin option, not a built-in PTK field.

Variant generators
------------------

Select one or more of the seven built-in variant generators::

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

Version generators
------------------

The bundled ``version.generate`` step supports C headers, CMake, MSBuild, Python
and JSON. See :doc:`/guides/versioning` for source selection, output configuration
and examples.
