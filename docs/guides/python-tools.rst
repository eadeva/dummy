Python scripts, environments and reusable tools
===============================================

Projects extend their behavior with ordinary commands and Python packages.
PTK supplies configuration, scheduling, logging and reporting; project tools
own their implementation. A package can be published to an Artifactory Python
repository, selected at a particular version and executed through uv without
being installed into PTK's own Python environment.

PTK does not provide a third-party plugin API. This is the accepted simplification
in :need:`DD_NO_PLUGIN_API`, implemented by :need:`REQ_Sw_EXTERNAL_TOOLS`.
Built-in operations, generators, credential providers, installers and report
formats remain available. The VS Code extension and Git hooks are separate
features and are unaffected by this decision.

Choose an execution mode
------------------------

The following examples are alternative step configurations. A step may omit
``python`` or select exactly one of ``project``, ``venv``, ``uvx`` and
``interpreter: cli``. ``python`` applies only to ``run`` steps. This contract is
recorded in :need:`DD_PYTHON_RUNTIME` and :need:`REQ_Sw_PYTHON_RUNTIME`.

.. list-table:: Python execution choices
   :header-rows: 1
   :widths: 22 36 42

   * - Choice
     - Step configuration
     - Execution
   * - Standalone script
     - ``run: [tools/check.py]``; omit ``python``
     - ``uv run --no-project tools/check.py``; supports PEP 723 metadata.
   * - PTK's interpreter
     - ``run: [tools/check.py]`` with ``python: {interpreter: cli}``
     - PTK's exact interpreter executes the script, with its existing packages.
   * - Requirements environment
     - ``run: [tools/check.py]`` with ``python: {venv: {...}}``
     - A reusable environment under the repository's ``.ptk/venvs``.
   * - uv project
     - ``run: [tools/check.py]`` with ``python: {project: .}``
     - ``uv run --project <resolved directory> python tools/check.py``.
   * - Packaged tool
     - ``run: [company-quality, check]`` with
       ``python: {uvx: company-quality==1.4.0}``
     - ``uv tool run --from company-quality==1.4.0 company-quality check``.
   * - Explicit interpreter
     - ``run: [python, tools/check.py]``; omit ``python``
     - Ordinary command lookup on the step's PATH, with no PTK Python setup.

Use argument lists to preserve paths containing spaces and argument boundaries.
The default working directory is the repository root; ``cwd`` changes it.
Script paths are relative to that working directory. In contrast,
``python.project`` and ``python.venv.requirements`` paths resolve from the
repository root. Selecting a project does not change the step's working directory.
PTK substitutions work in command arguments, for example
``run: [tools/check.py, --variant, "${vh.variant}"]``.

Plain command strings normally use the platform shell. Strings starting with a
recognized script, without shell operators, and all commands with ``python``
configured are split into arguments and run without a shell. Do not rely on
pipes, redirection or shell expansion inside a Python-mode command.

Standalone scripts and inline dependencies
------------------------------------------

In a job file::

   steps:
     check:
       run: [tools/check.py, --verbose]

PTK detects the leading ``.py`` path and invokes uv with ``--no-project``.
It does not automatically select the repository's Python project dependencies.
A script can declare its own Python requirement and dependencies using a PEP 723
header; uv handles those when running the file::

   # tools/check.py
   # /// script
   # requires-python = ">=3.12"
   # dependencies = ["rich==13.9.4"]
   # ///
   from rich import print

   print("Checking the project")

PTK does not create a separate requirements-based environment for this mode.
uv controls interpreter selection and any script dependency environment. Without
inline dependency metadata, do not assume that the script receives an isolated
environment. See `uv script execution <https://docs.astral.sh/uv/guides/scripts/>`_.

Use PTK's interpreter
---------------------

Choose this explicitly for scripts that should use the same interpreter and
installed dependencies as PTK::

   steps:
     check:
       python: {interpreter: cli}
       run: [tools/check.py]

PTK does not install script dependencies in this mode. A leading ``.py`` path
uses PTK's exact executable. For commands such as ``python -m package``, PTK
prepends its interpreter directory to PATH; an explicitly named absolute
interpreter still selects that executable.

Requirements and package environments
-------------------------------------

Declare requirement files, extra packages and an optional Python interpreter or
version request::

   steps:
     check:
       run: [tools/check.py]
       python:
         venv:
           python: "3.12"
           requirements: [requirements-tools.txt]
           packages: [rich==13.9.4]

The fields are optional; ``venv: {}`` requests an environment without additional
packages. PTK creates it with ``uv venv`` and installs declared dependencies with
``uv pip install``. Scripts use that environment's interpreter; ordinary commands
find its executables first on PATH. No shell activation is needed.

Environments live under ``.ptk/venvs/<hash>``. The hash covers the Python request,
declared package requirements, and the paths and bytes of the listed requirements
files. Changing only a file timestamp does not create another environment. Steps
with matching declarations share it. A completed environment is reused without
reinstalling dependencies on every invocation.

This is not a transitive dependency lock or an automatic upgrade mechanism.
Nested requirement/constraint files and local package source trees are not
recursively included in PTK's environment hash. Updating an unpinned package on
an index does not invalidate an existing environment. Projects must manage
dependency changes; use a uv project for local package development and lockfile
management. Index/authentication settings for environment creation are described
below.

uv projects and dependency groups
---------------------------------

Use the project's ``pyproject.toml`` and ``uv.lock``::

   steps:
     check:
       run: [tools/check.py]
       python:
         project: .
         groups: [quality]

``quality`` must be a dependency group declared by that project. PTK passes each
group as ``--group NAME``; uv's normal default groups still apply. ``groups`` is
valid only with ``project``. Omit it when no additional groups are needed.

PTK invokes ordinary ``uv run --project``. It does not add ``--locked``,
``--frozen`` or ``--no-sync``: uv may update the lockfile and synchronize the
environment before execution. A project that requires these flags can invoke
uv explicitly as an ordinary ``run`` command, without a ``python`` setting.

For a standalone project, the normal environment is its ``.venv`` directory.
An explicit step environment value can select another location::

   env:
     UV_PROJECT_ENVIRONMENT: ${project.root}/.ptk/venvs/quality

This is project configuration, not an automatic per-step environment. PTK rejects
unordered project-mode steps or workflow jobs that resolve to the same environment.
Declare a dependency or separate their environments; see :doc:`workflows` and
:doc:`/reference/execution`. Use absolute environment paths for uv workspace
members to account for uv's workspace-root discovery. Avoid pointing
synchronization at the environment running PTK. Dry runs show runtime selection
without creating environments.

Explicit interpreters, modules and inline code
----------------------------------------------

Omit ``python`` to use an existing interpreter as an ordinary command::

   steps:
     check:
       run: [python, tools/check.py]

This differs from ``run: [tools/check.py]``: the first executable is ``python``,
so PTK does not add uv. Lookup uses the resolved step PATH, which may differ from
the caller's PATH. Use an absolute executable path to select a particular
installation; paths are platform-specific.

Modules and small inline commands also use ordinary command arguments::

   run: [python, -m, my_package.check, --verbose]

or::

   run: [python, -c, "print('Hello')"]

They can also be combined with ``python.project`` or ``python.venv`` to use that
environment. These forms invoke Python rather than uv's direct script runner,
so they do not process a script's PEP 723 header. Script headers likewise do not
install dependencies in PTK's interpreter or a requirements-based environment.

Define a normal command
-----------------------

A package exposes an executable with the standard Python ``project.scripts``
metadata. It does not import PTK or register ``ptk.*`` entry points::

   # pyproject.toml
   [build-system]
   requires = ["hatchling>=1.24"]
   build-backend = "hatchling.build"

   [project]
   name = "company-quality"
   version = "1.4.0"
   requires-python = ">=3.12"

   [project.scripts]
   company-quality = "company_quality.cli:main"

   [tool.hatch.build.targets.wheel]
   packages = ["company_quality"]

Implement normal argument parsing, stdout/stderr output and exit codes in that
package. Its main function returns zero for success and a nonzero status for
failure. The runnable ``examples/python-tool`` starter checks for a required
file; ``tests/test_python_tool_package.py`` builds its real wheel and runs it
through PTK and uv in an offline temporary project, checking both success and
failure. This does not require any PTK Python API dependency in the tool package.

Editable local packages
-----------------------

``python.project`` also supports local development without building and
publishing a wheel for each source edit. For a packaged project in
``tools/company-quality``::

   steps:
     quality:
       python: {project: tools/company-quality}
       run: [company-quality, check]

The directory must contain the package and a ``pyproject.toml`` with a build
system supporting editable installs, such as the example above. Its
``project.scripts`` entry defines the executable. Alternatively use
``run: [python, -m, company_quality]`` if the package provides ``__main__.py``.

uv normally installs the project in editable mode, so changes to Python source
are picked up on subsequent execution. PTK does not add an ``editable`` flag or
perform a manual ``pip install -e`` step. A project without a build system is not
installed as a package by default; standalone script files can still be run
directly. See `uv editable installation
<https://docs.astral.sh/uv/concepts/projects/sync/#editable-installation>`_.

Dependency, entry-point or build-metadata changes can require environment
synchronization; compiled extensions may require rebuilding. Editable mode is
not a live reload facility for an already running application. ``uvx`` with a
local wheel uses that built artifact, not an editable link to its sources.

Run a published package
-----------------------

In ``jobs/verify.ptk.yml``::

   steps:
     quality:
       python:
         uvx: company-quality==1.4.0
       run: [company-quality, check]

PTK invokes ``uv tool run --from company-quality==1.4.0 company-quality check``.
uv manages the tool's dependencies in its own environment/cache. No permanent
``uv tool install`` is required for this step. The package and executable may have
different names, as shown in the starter. For local development, the ``uvx``
requirement can also identify a built wheel.

Use ``python.with`` to add packages to the uv tool environment::

   python:
     uvx: company-quality==1.4.0
     with: [rich==13.9.4]
   run: [company-quality, check]

``with`` is only valid with ``uvx``. A leading script path is also supported::

   python: {uvx: rich==13.9.4}
   run: [tools/check.py]

For this form PTK runs ``uv run --no-project --with rich==13.9.4 python
tools/check.py``, adding any ``with`` packages. The script's inline dependency
header is not used to install dependencies in this form.

Use ``python.project`` for a uv-managed project whose dependency groups and lock
file should govern execution, or ``python.venv`` for configured requirement
files/packages. Use ``python.interpreter: cli`` only when deliberately selecting
PTK's own environment. These modes are mutually exclusive; the schema and
:doc:`configuration` describe their fields.

Configure Artifactory as a Python index
---------------------------------------

Publish wheels and/or source distributions to an Artifactory PyPI repository.
Configure uv to use its Python simple-index endpoint, for example::

   steps:
     quality:
       python: {uvx: company-quality==1.4.0}
       run: [company-quality, check]
       env:
         UV_DEFAULT_INDEX: https://artifacts.example.org/artifactory/api/pypi/python-virtual/simple

The URL is illustrative. The selected repository must provide the tool and its
required dependencies, directly or through an Artifactory virtual/proxy repository.
Provide authentication through uv's supported credential configuration or secret
environment variables; never embed credentials in the committed index URL.
PTK's artifact destination/download configuration does not configure uv's Python
index automatically.

For ``uvx`` command steps, uv receives the resolved command environment. The
``python.venv`` setup currently uses the launcher environment before the command
starts; configure index/authentication at launcher or user level for that mode.
This distinction is existing behavior, not a promise that every step environment
value participates in environment creation.

Passing configuration and reporting results
-------------------------------------------

Pass context explicitly through arguments, environment variables and documented
files. For example, a selected variant's feature can become a tool argument::

   steps:
     configure:
       python: {uvx: company-config==1.4.0}
       run:
       - company-config
       - --mode
       - ${vh.features.motor.CONTROL_MODE}
       - --output
       - ${run.build_dir}/company-config.json

There is no external callback receiving PTK's internal resolved-variant object.
Choose the specific feature/data values or built-in generated files that the
command needs. PTK does not automatically create a generic external generator
protocol. Built-in ``generators: [make, cmake, bazel, gn]`` still run before the
command and retain their existing step-folder contract; see
:doc:`variant-generation`.

For reports, produce supported result files such as JUnit XML, Cobertura XML or
SARIF in the step's report directory, or import them with ``report.import``.
For another report format, export PTK's JSON and process it with a separate tool.
A converter must preserve the source tool's meaning and failure status; merely
writing a successful JUnit file must not conceal a failed command. See
:doc:`log-analysis` and :doc:`/reference/builtins`.

Compatibility and versioning
-----------------------------

Ordinary tools own their versions and declare their own dependencies. Pin the
package version in PTK configuration, or use a locked uv project when dependency
reproducibility requires more than pinning the top-level package. PTK does not
promise that a version pin alone freezes every transitive dependency.

Removing the plugin API eliminates registration/discovery, collisions, dynamic
service replacement, cross-project plugin state, and third-party compatibility
obligations for PTK's internal Python classes and callable signatures. Tool
packages can evolve independently and use separate dependency environments.

This does not remove all compatibility concerns. PTK still versions its CLI,
configuration, editor protocols and report/file contracts. Tools still need stable
arguments, environment and output formats. Changes to those contracts need
explicit decisions and tests. PTK has not been rolled out and has no external
plugin consumers to support. Plugin support is removed outright, without
migration code, legacy loading, compatibility aliases or fallback behavior.
Unsupported settings use ordinary configuration validation; the editor retains
access to the source YAML and diagnostics.

Execution responsibility
------------------------

uv must be available for standalone script, project, venv and uvx execution.
PTK checks the launcher's ``PTK_UV`` override, PATH and common user uv installation
directories. It does not install uv automatically in this adapter. uv may need
network access for Python, packages or build dependencies; offline execution
requires those resources to be available already. PTK's interpreter and explicit
interpreter commands do not need uv for their Python execution.

All modes run separate processes. Normal steps use the common arguments,
environment/secrets, output capture, exit status, timeout and reporting behavior.
For a Python GUI, set job-level ``gui: true``; only its final launch command is
detached. PTK exits without waiting for the GUI or collecting its later output.
See :ref:`gui-jobs` for preparation and lifecycle constraints.

Python dependency environments and the optional PTK output cache are separate.
The output cache does not automatically hash script/package source files or all
installed dependencies. Editable source changes alone can therefore leave an
otherwise matching dependent step reusable. During development, use
``--no-cache-ptk`` to force execution, leave that step's cache disabled, or have
an always-running prerequisite declare the relevant sources as outputs for
fingerprinting. ``--no-cache-ptk`` does not rebuild Python environments or clear
uv's caches. Projects own input coverage; see :doc:`output-reuse`.

A separate Python dependency environment is not a filesystem or network sandbox.
Project commands retain the user's permissions and own artifact correctness,
shared-resource coordination, repeatable retries, cancellation cleanup and any
necessary rollback. PTK observes exit status and captured evidence. This preserves
project flexibility under :need:`DD_EXECUTION_BOUNDARIES`.

Reference: `uv tool execution <https://docs.astral.sh/uv/concepts/tools/>`_ and
`uv package indexes <https://docs.astral.sh/uv/concepts/indexes/>`_.
