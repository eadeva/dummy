Reusable Python tools
=====================

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

A separate Python dependency environment is not a filesystem or network sandbox.
Project commands retain the user's permissions and own artifact correctness,
shared-resource coordination, repeatable retries, cancellation cleanup and any
necessary rollback. PTK observes exit status and captured evidence. This preserves
project flexibility under :need:`DD_EXECUTION_BOUNDARIES`.

Reference: `uv tool execution <https://docs.astral.sh/uv/concepts/tools/>`_ and
`uv package indexes <https://docs.astral.sh/uv/concepts/indexes/>`_.
