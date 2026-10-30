Built-in operations and generators
==================================

PTK ships a fixed set of operations selected through ``uses``. Use ``run`` with
an external command or Python package for project-specific behavior; see
:doc:`/guides/python-tools`. The schema lists the supported operation and generator
names. Unknown names are configuration errors, including in skipped steps.

Basic operations
----------------

* ``echo`` writes ``with.message`` to the step log.
* ``wait`` waits for ``with.seconds`` while observing cancellation.
* ``report.import`` copies supported tool result files into the step report
  folder. Its options and supported formats are in :doc:`/guides/log-analysis`.
* ``version.generate`` writes version files; see :doc:`/guides/versioning`.

Variant generators
------------------

Select built-in generators directly on a step::

   steps:
     configure:
       generators: [cmake, header]
       run: [cmake, -S, ., -B, "${run.build_dir}/cmake", "-DPTK_VARIANT_FILE=${run.build_dir}/variant.cmake"]

A step may instead contain only ``generators``. Generation requires a valid
concrete variant and precedes every command or built-in operation attempt. The eight built-ins
are ``header``, ``cmake``, ``bazel``, ``gn``, ``make``, ``yocto``, ``robot`` and
``sphinx``. Outputs always belong to the step's build directory. The former
``uses: variant.generate`` interface and its output override are removed.

See :doc:`/guides/variant-generation` for the data contract, escaping restrictions,
project responsibilities, native build integration and downloadable Bazel helper.
PTK validates generated paths/content before writing, rejects colliding names
and directory/file conflicts, and replaces each file atomically. There is no
transaction across multiple files. Additional generation logic belongs in an
ordinary command with explicit inputs and outputs.

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
