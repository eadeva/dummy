PTK — project tool kit
======================

PTK turns repository configuration into a command-line interface for jobs,
variants and local workflows. It prepares tools and isolated environments,
captures execution logs, and imports tool results into reports. The same
configuration drives developer commands and CI jobs.

Start with :doc:`guides/getting-started`, then use
:doc:`reference/cli` for command syntax and :doc:`guides/configuration` for
file ownership and authoring. Python 3.12 or newer is required.

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   guides/index
   requirements/index
   architecture/index
   reference/index
   ci/index

About this documentation
------------------------

The guides describe current behavior. The requirements distinguish agreed needs
from implementation-derived requirements awaiting review; future work is
explicitly identified. Architecture follows the twelve arc42 sections and
explains the current implementation and its limits.

The CLI is the requirements scope. The editor guide documents integration with
PTK, but this set does not specify the VS Code extension's user interface.
Legacy documentation and the previous development plan are retained outside this
site under ``reference/`` in the source checkout. They are historical reference,
not current command or configuration specifications.
