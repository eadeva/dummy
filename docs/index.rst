ptk — project tool kit
======================

ptk turns project configuration into a CLI with typed parameters, variants,
isolated command environments, logs and reports. Python 3.12 or newer is required.

.. toctree::
   :maxdepth: 2

   quickstart
   cli
   configuration
   workflows
   versioning
   artifacts
   m11
   plugins
   reference
   skills
   editor
   packaging
   development
   performance

The implementation roadmap is maintained separately in ``docs/PLAN.md``.

Current capability guide
------------------------

* Configuration discovery, init, variants, job parameters, maintainers,
  environment isolation, tool sources and report behavior: :doc:`configuration`.
* Local job orchestration, VMR call ownership and VS Code workflow tasks:
  :doc:`workflows`.
* Project/component versions, VMR dependencies, environment variables and generated
  build files: :doc:`versioning`.
* Commands and credential/setup entry points: :doc:`cli`; built-ins and extension
  contracts: :doc:`plugins`.
* Background step boundaries: :doc:`m11`.
* Package preparation without publishing: :doc:`packaging`.
* Offline authoring resources, protected updates and editor tasks: :doc:`editor`;
  task-specific assistant instructions: :doc:`skills`.
* Every supported configuration field and its default: :doc:`reference`.
