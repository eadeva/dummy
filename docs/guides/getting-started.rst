Run your first project
======================

Install the team-provided PTK package with its installer; see
:doc:`/guides/packaging` for package sources and local development. Then check
``ptk --version`` in a new shell. The examples below use the installed CLI.

When working on PTK itself, run ``uv sync`` from its source checkout to install
the development dependencies. This is separate from initializing a consuming
project.

Join an existing project
------------------------

Use the team-provided PTK launcher and check ``ptk --version``, ``ptk --help``
and ``ptk validate`` from the checkout. Read :doc:`local-setup` for tools, local
hooks and troubleshooting. Do not run ``ptk init`` over an existing project.
A project can have entirely different jobs, variants and configuration paths
from the examples below; use its help or ``ptk describe --json`` to discover them.

Create your own project
-----------------------

From the installed CLI, preview and initialize a new directory::

   ptk init my-project --name "My project" --config-dir config/ptk --dry-run
   ptk init my-project --name "My project" --config-dir config/ptk
   cd my-project
   ptk validate
   ptk hello --message "It works"
   ptk -V release build

The configuration folder must be supplied by the user. Omit ``--config-dir`` on
a terminal to enter it at the prompt; there is no default. Scripts, redirected
input and ``--yes`` require ``--config-dir PATH``. The path is relative to the
repository root, including when the same choice is applied to multiple VMR
repositories. The root
``.main.ptk.yml`` contains only repository metadata.
The chosen directory contains ``project.ptk.yml`` for project settings, plus:

* ``jobs/hello.ptk.yml`` and ``jobs/build.ptk.yml`` for runnable jobs.
* ``project.variants.ptk.yml`` and ``variants/debug.ptk.yml`` / ``variants/release.ptk.yml``.
* ``tools.ptk.yml``, ``versioning.ptk.yml``, ``credentials.ptk.yml`` and ``configs.ptk.yml``.
* ``folder_structure.ptk.yml`` and ``workflows/verify.ptk.yml``.
* ``maintainers.ptk.yml`` for the independent identity list.
* A generated ``README.md`` with commands, ownership guidance and relative links
  to the installed expert agent, skills, offline docs and schema.

Init also installs the version-matched assistant bundle in ``.github/agents``,
``.github/skills`` and ``.github/ptk``. It works offline with packaged resources;
no separate sync command is needed on first initialization. Assistant discovery
depends on the editor. Installation does not execute skills or grant permissions.

The example core component is registered at ``components/core``. Its
``component.variants.ptk.yml`` lives there beside the future build definition.
Project settings include the shared environment. Files contain their section
bodies; filenames provide job, workflow and variant identities. Optional files
can be omitted. No secrets, tools or Git tags are needed for the starter.

The starter has debug/release variants and a literal ``0.1.0`` version, so it
runs without tools, credentials or Git tags. ``hello`` demonstrates parameters
and version substitutions; ``build`` generates ``_bin/<variant>/build/generated/version.h`` and
``version.cmake``. Each run also writes its ignored ``.gen.version.ptk.yml``
snapshot. See :doc:`/guides/versioning` to select Git tags or existing manifests instead.

No existing configuration file is overwritten; all destinations are checked
before writing. The config README is managed with the assistant bundle;
keep project-specific guidance separately. Existing assistant-file collisions also
stop init before writes. The bundle includes provenance for subsequent
``ptk maintainer sync agent`` updates, which protect locally edited files.
In a VMR, each newly initialized repository receives its own bundle.
Existing ``.gitignore`` content is kept and missing PTK ignore
rules are appended. The project name defaults to the destination directory name.

The command works without an existing project, including inside a directory
whose parent contains a ptk project. ``DIRECTORY`` is the initialization target;
do not combine this command with global ``--set`` overrides.
Outside a VMR, ``ptk init`` initializes the current directory. In a VMR,
it initializes all checked-out members without a root ``.main.ptk.yml``, skips
configured repositories, and asks for the common config folder once.
Use an explicit DIRECTORY to initialize only one project.

Run the repository example
--------------------------

The quickstart uses only the Python interpreter running ptk. It needs no CMake,
compiler, credentials, or network connection once ptk is installed. Commands
below work on Linux and Windows. Copy ``examples/quickstart`` outside this Git
checkout, then open a terminal in the copy. When using installed authoring
resources, the same example is under ``.github/ptk/examples/quickstart``; copy it
out of the managed reference directory first. PTK discovers its root marker::

   ptk validate
   ptk -V debug build --dry-run
   ptk -V debug build --message "Hello from ptk"
   ptk -V release build

``dry-run`` displays the commands without executing the steps. ``build`` first
writes ``_bin/<variant>/build/message.txt`` under the copied project, then runs a parallel
check set. The extra check is enabled for ``debug`` and skipped for ``release``.
The unit check writes JUnit XML which ptk imports into its report.

Inspect the results
-------------------

Open ``_reports/debug/build/report.html`` under the copied project in a browser, or::

   ptk -V debug report open build

JSON, JUnit XML and Markdown reports are written alongside the HTML. Logs are in
``_logs/debug/build`` under the copy. Previous logs are retained according
to the project's history setting.

Read the configuration and workload
-----------------------------------

.. literalinclude:: ../../examples/quickstart/.main.ptk.yml
   :language: yaml

.. literalinclude:: ../../examples/quickstart/config/ptk/jobs/build.ptk.yml
   :language: yaml

.. literalinclude:: ../../examples/quickstart/demo.py
   :language: python

In PTK's source checkout only, the larger ``examples/demo`` directory illustrates a firmware configuration.
Its CMake presets, toolchains and upload scripts are project-specific placeholders;
it is suitable for configuration validation and dry runs, not an unattended build.

Configuration-directory starter
--------------------------------

Copy ``examples/authoring`` into a new repository. Its root entry file declares
its configuration directory explicitly:

.. literalinclude:: ../../examples/authoring/.main.ptk.yml
   :language: yaml

From that repository, run ``ptk validate``, ``ptk build --dry-run``
and ``ptk build --all-variants``. These commands are exercised by the authoring
skill tests, including invocation from the configuration subdirectory.
