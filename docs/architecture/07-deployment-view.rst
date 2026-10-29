Deployment view
===============

A normal installation puts the Python package and its entry point in a
user-scoped tool environment. The install scripts orchestrate installation;
PTK's ``self-service`` commands perform completion and editor setup. Project
job environments are separate from the environment running PTK.

.. list-table:: Deployment artifacts
   :header-rows: 1
   :widths: 25 45 30

   * - Artifact
     - Purpose
     - Consumer prerequisites
   * - Python wheel
     - CLI, runtime modules, built-in resources, offline authoring material and prepared VSIX
     - Compatible Python and package dependencies
   * - Source distribution
     - Rebuildable Python package with frozen version and prepared assets
     - Build backend/dependencies; no Git history required for the frozen version
   * - Installer scripts
     - Select package source and configure the current user's installation
     - Supported shell, Python/tool installer and source access
   * - VSIX
     - Optional editor integration installed from the matching package resource
     - VS Code command when editor installation is requested
   * - HTML documentation
     - Browsable guides, requirements, architecture and reference
     - Browser; no Python runtime needed to read it

Completion is per shell profile and per user, not attached to a virtualenv
activation or terminal application. Existing terminals may need to reload their
profile. Shell completion invokes the ``ptk`` found on that shell's PATH; a
stale installation can therefore expose stale commands.

Source-checkout development uses editable Python installation and the extension
build job. Node/npm and Sphinx are development/release dependencies, not runtime
requirements for installing a prepared wheel. See :doc:`/guides/packaging`.

The installer currently refreshes its selected Python package source. The
request to retain an already newer PTK Python package is tracked as
:need:`REQ_Sw_KEEP_NEWER_PACKAGE`; extension version protection is a separate
implemented behavior. Do not infer package downgrade protection from the VSIX
check.
