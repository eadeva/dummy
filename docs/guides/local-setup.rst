Local setup and job preflight
=============================

This guide applies to a repository using PTK, including a fresh checkout.
Use the team's installed PTK executable or documented launcher. Do not assume
this repository is PTK's own source or run ``uv sync`` unless the project actually
uses a uv environment for PTK. ``uv.lock`` belongs beside its Python project's
``pyproject.toml``; PTK does not relocate that lock into its configuration folder.

Start without running a job::

   ptk --version
   ptk --help
   ptk describe --json
   ptk validate

Use discovered job and variant names in the commands below. ``JOB`` is a
placeholder, not a built-in job. A project without variants is valid. In a VMR,
use the owning repository's invocation route; keep global options before its alias.

What a real local job checks
----------------------------

.. list-table:: Preparation and execution boundaries
   :header-rows: 1
   :widths: 25 75

   * - Check
     - Behavior
   * - Configuration and access
     - Validate configuration/dependencies, job audience, parameters, substitutions and variant eligibility.
   * - Required tools
     - Check declared job requirements in the selected environment and enforce configured versions. Missing or incompatible tools block execution.
   * - Credentials
     - Resolve secrets needed by selected, non-skipped steps before they start. Do not expose their values in diagnosis.
   * - Known shared resources
     - Reject recognized incompatible parallel Python environments/output identities; acquire the job/variant execution lock.
   * - Local Git hooks
     - When enabled, verify installation and repair missing/broken hooks before running steps. Failure blocks the job.
   * - Step environment
     - Prepare the selected Python runtime when its step starts; recheck required tools in the actual command environment.

These checks do not prove arbitrary input files, remote services or hardware are
ready. Put project-specific readiness checks in explicit steps. PTK does not
infer tools from executable names in commands. It does not run lint hooks simply
because a job starts, or automatically synchronize/check external configuration
freshness. Use ``ptk validate --generated`` when that check is wanted.

A dry run skips job steps, hook installation and tool installation, but configured
version-discovery commands can still execute during preparation. Graph-only
inspection avoids command preparation. Do not use a preview as a general sandbox.

Missing tools
-------------

Declare tools in the project's ``tools.ptk.yml`` and require them through the job's
``requires_tools``. Normal execution checks but does not install them without
asking: in an interactive terminal (not CX), a job with missing or too old tools
lists them and asks **Install them now?**; answering yes installs them like
``--setup`` and continues, no keeps the usual error. Without a terminal the job
fails with that error. To preview or request installation explicitly::

   ptk self-service tools --job JOB --dry-run
   ptk self-service tools --job JOB
   ptk JOB --setup

Installation requires a supported configured source and access to it. System
package managers and Chocolatey bootstrap require their explicit options. PTK
supports configured Chocolatey, uv-tool, downloads, apt/dnf, Toolbase and Artifactory
sources with platform-specific limits; mise is not currently a built-in installer.
See :doc:`configuration` for the exact schema and tool source contracts.

A job containing ``tools.ensure`` defers the initial required-tool check so that
step can prepare tools. Put it before consuming commands using ``needs``; YAML
order alone does not order execution. A skipped ensure step does not install.
An undeclared command's missing executable is detected when that command runs.

Inside Docker
-------------

PTK checks tools and versions inside the container. Per-tool ``docker: false``
(the default) disables installation there, not validation. Even with ``--setup``,
the image must already provide an acceptable tool unless installation is explicitly
allowed. Each affected tool is reported, for example::

   tool 'cmake' is unavailable in the Docker image: not found.
   Add or update this tool in the image; installation disabled inside Docker (docker: false)

An installed tool that fails its version requirement is reported as incompatible,
with the check's reason. Review the image or its PATH before allowing an installer.
``docker: true`` permits configured installation; it does not build or start a
container. ``PTK_DOCKER=1|0`` overrides best-effort container detection.

Local pre-commit hooks
----------------------

In the project's ``configs.ptk.yml``, enable::

   pre-commit:
     enabled: true

Commit the final pre-commit configuration (project-owned or generated from
explicit external mappings). By default it is ``.pre-commit-config.yaml`` at the
repository root; ``hook_config`` selects another relative path.

When enabled, every real local job verifies hook installation and repairs it
when necessary.
Local workflows check participating repositories before starting jobs. A working
installation is reused. All developers can use this behavior without maintainer
rights. PTK creates a dedicated pre-commit environment under the Git common
directory; hook-tool environments may be downloaded on first use.

For explicit installation and inspection::

   ptk self-service hooks install
   ptk self-service hooks status

A fresh clone alone cannot run PTK's setup. Opening the extension alone does not
install hooks; running a job through it uses the normal check. Help and dry runs
also do not install hooks. For developers who commit before their first job,
include explicit hook installation in the team's local onboarding instructions.
To execute checks immediately, use ``ptk pre-commit run --all-files``.

Missing configuration or conflicting Git hook settings block setup. PTK preserves
existing hooks where supported and refuses unsafe collisions; see
:doc:`configuration` for worktrees, custom hook paths and conflict handling.

External configuration ownership
--------------------------------

Base synchronization remains maintainer-only. Developers use committed copies;
job startup never fetches the external repository. The provenance lock lives at
``<repository.config_path>/.ptk-configs.lock.json``. Files remain writable; content
hashes detect changes and synchronization refuses to overwrite local edits.

Use ``ptk validate --generated`` to check freshness offline. Maintainers can write
``ptk maintainer configs-report`` to inspect current generated-output deviations
and a separate list of modified base filenames. See :doc:`shared-configs` for
pinning, ownership and report limitations.
