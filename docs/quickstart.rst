Run your first project
======================

From the repository root, install ptk and its development dependencies::

   uv sync

The quickstart uses only the Python interpreter running ptk. It needs no CMake,
compiler, credentials, or network connection once ptk is installed. Commands
below work from the repository root on Linux and Windows::

   uv run ptk -c examples/quickstart/main.ptk.yml config validate
   uv run ptk -c examples/quickstart/main.ptk.yml dry-run build -V debug
   uv run ptk -c examples/quickstart/main.ptk.yml build -V debug --message "Hello from ptk"
   uv run ptk -c examples/quickstart/main.ptk.yml build -V release

``dry-run`` displays the commands without executing the steps. ``build`` first
writes ``examples/quickstart/_bin/<variant>/message.txt``, then runs a parallel
check set. The extra check is enabled for ``debug`` and skipped for ``release``.
The unit check writes JUnit XML which ptk imports into its report.

Inspect the results
-------------------

Open ``examples/quickstart/_reports/debug/build/report.html`` in a browser, or::

   uv run ptk -c examples/quickstart/main.ptk.yml report open build -V debug

JSON, JUnit XML and Markdown reports are written alongside the HTML. Logs are in
``examples/quickstart/_logs/debug/build``. Previous logs are retained according
to the project's history setting.

Read the configuration and workload
-----------------------------------

.. literalinclude:: ../examples/quickstart/main.ptk.yml
   :language: yaml

.. literalinclude:: ../examples/quickstart/demo.py
   :language: python

The larger ``examples/demo`` directory illustrates a firmware configuration.
Its CMake presets, toolchains and upload scripts are project-specific placeholders;
it is suitable for configuration validation and dry runs, not an unattended build.
