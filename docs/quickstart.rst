Run your first project
======================

From the repository root, install ptk and its development dependencies::

   uv sync

Create your own project
-----------------------

From the installed CLI, preview and initialize a new directory::

   ptk setup init my-project --name "My project" --dry-run
   ptk setup init my-project --name "My project"
   cd my-project
   ptk setup config validate
   ptk hello --message "It works"
   ptk build -V release

The terminal wizard asks where configuration files should live (default ``ptk``).
Use ``--config-dir config/ptk --yes`` for an unattended setup; redirected input
also uses the default unless ``--config-dir`` is supplied. The root
``.main.ptk.yml`` contains only repository metadata and the project include.
The chosen directory contains ``project.ptk.yml`` as its include index, plus:

* ``actions/hello.ptk.yml`` and ``actions/build.ptk.yml``: two independent actions.
  ``actions/*.ptk.yml`` loads additional action files automatically.
* ``variants/variants.ptk.yml``: component/feature model and default selection;
  includes ``debug.ptk.yml`` and ``release.ptk.yml`` from the same folder.
* ``tools/tools.ptk.yml`` and ``versioning/versioning.ptk.yml``.
* ``environment/environment.ptk.yml`` and ``credentials/credentials.ptk.yml``.
* ``configs/configs.ptk.yml`` for shared formatter/linter settings.

``cx.ptk.yml`` and ``maintainers.ptk.yml`` stay at the configuration root because
they are conventional discovery entry points. Other nested files are loaded by
explicit includes. Optional settings contain commented field examples and usage
notes, including managed tools, credential providers, Git versions and action
requirements; no secret values or tool installations are needed.

The starter has debug/release variants and a literal ``0.1.0`` version, so it
runs without tools, credentials or Git tags. ``hello`` demonstrates parameters
and version substitutions; ``build`` generates ``_bin/<variant>/generated/version.h`` and
``version.cmake``. Each run also writes its ignored ``.gen.version.ptk.yml``
snapshot. See :doc:`versioning` to select Git tags or existing manifests instead.

No existing configuration file is overwritten; all destinations are checked
before writing. Existing ``.gitignore`` content is kept and missing PTK ignore
rules are appended. The project name defaults to the destination directory name.

The command works without an existing project, including inside a directory
whose parent contains a ptk project. ``DIRECTORY`` is the initialization target;
do not combine this command with global ``--config`` or ``--set`` options.
Bare ``ptk setup init`` initializes the current directory; ``ptk init`` is an alias.

Run the repository example
--------------------------

The quickstart uses only the Python interpreter running ptk. It needs no CMake,
compiler, credentials, or network connection once ptk is installed. Commands
below work from the repository root on Linux and Windows::

   uv run ptk -c examples/quickstart/.main.ptk.yml config validate
   uv run ptk -c examples/quickstart/.main.ptk.yml dry-run build -V debug
   uv run ptk -c examples/quickstart/.main.ptk.yml build -V debug --message "Hello from ptk"
   uv run ptk -c examples/quickstart/.main.ptk.yml build -V release

``dry-run`` displays the commands without executing the steps. ``build`` first
writes ``examples/quickstart/_bin/<variant>/message.txt``, then runs a parallel
check set. The extra check is enabled for ``debug`` and skipped for ``release``.
The unit check writes JUnit XML which ptk imports into its report.

Inspect the results
-------------------

Open ``examples/quickstart/_reports/debug/build/report.html`` in a browser, or::

   uv run ptk -c examples/quickstart/.main.ptk.yml report open build -V debug

JSON, JUnit XML and Markdown reports are written alongside the HTML. Logs are in
``examples/quickstart/_logs/debug/build``. Previous logs are retained according
to the project's history setting.

Read the configuration and workload
-----------------------------------

.. literalinclude:: ../examples/quickstart/.main.ptk.yml
   :language: yaml

.. literalinclude:: ../examples/quickstart/demo.py
   :language: python

The larger ``examples/demo`` directory illustrates a firmware configuration.
Its CMake presets, toolchains and upload scripts are project-specific placeholders;
it is suitable for configuration validation and dry runs, not an unattended build.

Configuration-directory starter
--------------------------------

Copy ``examples/authoring`` into a new repository. Its root entry file declares
its configuration directory explicitly:

.. literalinclude:: ../examples/authoring/.main.ptk.yml
   :language: yaml

From that repository, run ``ptk setup config validate``, ``ptk dry-run build``
and ``ptk build --all-variants``. These commands are exercised by the authoring
skill tests, including invocation from the configuration subdirectory.
