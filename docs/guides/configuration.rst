Authoring configuration
=======================

Files and ownership
-------------------

Keep ``.main.ptk.yml`` at the repository root::

   repository:
     alias: firmware
     config_path: config/ptk
   schema_version: 1

The marker owns repository metadata and optional ``ptk_version`` requirements.
``config_path`` is an existing relative configuration directory inside the repository.
PTK loads only the following conventional documents there. Files are optional
except ``project.ptk.yml``, which must define the project name.

.. list-table:: Conventional configuration directory
   :header-rows: 1

   * - File
     - Contents
   * - ``project.ptk.yml``
     - Name, description, default job, component directories, variables and shared execution defaults
   * - ``folder_structure.ptk.yml``
     - Output layout
   * - ``artifactory_paths.ptk.yml``
     - Artifact destination rules
   * - ``credentials.ptk.yml``
     - Credential declarations
   * - ``tools.ptk.yml``
     - Tool declarations
   * - ``versioning.ptk.yml``
     - Version sources and generation rules
   * - ``configs.ptk.yml``
     - Shared formatter/linter settings
   * - ``project.variants.ptk.yml``
     - Default variant, project constraints and variant environment settings
   * - ``variants/<name>.ptk.yml``
     - One named variant
   * - ``jobs/<name>.ptk.yml``
     - One named job
   * - ``workflows/<name>.ptk.yml``
     - One named workflow
   * - ``maintainers.ptk.yml``
     - Independent maintainer identity list

Documents contain their section body; filenames supply entity names::

   # config/ptk/jobs/build.ptk.yml
   help: Build the project
   steps:
     - compile: {run: make}

PTK assembles this as ``jobs.build``. There are no includes, file precedence or
implicit CI/local overlays. An entity cannot be split across files. Unsupported
``.ptk.yml`` or ``.ptk.yaml`` filenames at the configuration root or in the owned
entity directories are errors. Entity directories contain files directly, without
nested configuration folders. Other repository files are not scanned.
Explicit CLI ``--set`` overrides, shared job defaults and variant inheritance
retain their model behavior. CI conditions and ``only_cx`` control execution.

Components own their feature definitions next to their code. Register their
repository-relative directories in ``project.ptk.yml``::

   name: firmware
   default_job: build
   components:
     networking: {path: src/networking}
     diagnostics: {path: src/diagnostics}

PTK reads ``src/networking/component.variants.ptk.yml`` next to that component's
``CMakeLists.txt`` or Bazel module::

   description: Network stack
   features:
     TLS: {type: bool}
   requires_components: [diagnostics]
   constraints:
     - {expr: TLS, message: Enable TLS when networking is selected}

Component files own features, dependencies and local constraints. Project variants
select components and feature values. Local constraints apply when their component
is selected; references across components are validated after assembly. Missing
component files describe an empty component and can be created when features are
added. A directory can be registered once. Paths must remain inside the repository
and cannot traverse symbolic links. The registration is literal, not a template.

Every value retains its source file and line. ``ptk validate`` checks
individual documents and then references across the assembled model;
``ptk maintainer config show --sources`` explains effective values. Commands and output
paths remain relative to the repository root.

Project discovery searches upwards and stops at a Git repository boundary.
The marker name remains exactly ``.main.ptk.yml``. A manual VMR has a separate
workspace marker containing ``virtual_monorepo: true`` and optional
``members: [nested/repository, other]``. Without members, only direct children are
checked. Git-repo workspaces use ``.repo/project.list``. A project can set
``virtual_monorepo: false`` in its marker to remain standalone. Discovery metadata
cannot be overridden through CLI settings. Workspace orchestration uses
``workflows/<name>.ptk.yml`` at the VMR root; see :doc:`/guides/workflows`.

The extension consumes PTK's schemas, document ownership, source locations and
validation errors through ``describe --json --configuration``. It creates the
owning file when needed and uses the correct section schema for raw-file forms.
The root schema from ``ptk maintainer config schema`` describes the assembled model;
individual file schemas are exposed in the configuration inventory.

Git substitutions
-----------------

Runtime templates support Git metadata independently of versioning configuration::

   # config/ptk/jobs/package.ptk.yml
   steps:
   - package:
       uses: echo
       with:
         message: "Source ${git.branch} at ${git.short_commit}"

Available fields:

* ``git.commit``: full source commit hash. In GitHub pull request workflows this
  is ``pull_request.head.sha`` from the local event payload, including
  ``pull_request_target``. It is not GitHub's synthetic merge or base commit.
* ``git.short_commit``: the first 12 hexadecimal characters of ``git.commit``.
* ``git.checkout_commit`` and ``git.short_checkout_commit``: the actual local
  ``HEAD``, full and 12-character forms. This identifies the merged code being
  tested when CI checks out a synthetic merge.
* ``git.branch``: the PR head branch for pull request events, otherwise the local
  branch or matching GitHub branch-event name. An unlabelled detached HEAD has
  an empty branch name. Use this field instead of ``project.current_branch``,
  which is not defined.
* ``git.tags``: sorted exact tags on the source commit. Annotated and lightweight
  tags are supported. With no exact tag, the value is an empty list.
* ``git.tag``: the triggering tag for a matching GitHub tag event, otherwise the
  first sorted exact tag. With no tag it is an empty string, not an error and
  not the nearest ancestor tag used by Git version discovery.
* ``git.dirty``: whether the checkout has tracked modifications, including
  staged changes. Untracked files do not affect it.

These values resolve during job preparation (including dry runs) or Artifactory
destination resolution and are reused throughout that operation. No Git process
is started until a template uses ``git.*``. Tag queries and working-tree status
are separately lazy and cached: using only ``git.short_commit`` does not scan
the working tree or enumerate tags. No network request, fetch or repository
mutation occurs. The next run reads fresh metadata.

Only locally available tags are considered, except for the matching tag event's
own tag. A shallow checkout can therefore have no known tag. If a PR head object
is not present locally, its hash and branch still come from the event and its
tag list is empty. Missing or invalid PR head metadata produces an explicit
error; PTK never substitutes the merge/base hash for it. GitHub context is scoped
to the workflow repository, not unrelated VMR members. Projects without a Git
checkout still work unless they request Git variables.

Date and time substitutions
---------------------------

Use ``${date.timestamp}`` for a value such as ``2026_10_26_1507``. The timestamp
is captured once at CLI invocation in the machine's local timezone. Every job,
variant and child of a local workflow in that invocation shares the same instant.
``${date.utc.timestamp}`` expresses that instant in UTC, including date rollover.
This works in runtime template values: variables, parameter defaults, environment,
step commands/options and :doc:`Artifactory destination paths </guides/artifacts>`.
Configuration discovery fields and other literal schema fields are not templates.

Available fields are ``timestamp`` (minute precision), ``timestamp_seconds``,
``iso`` (ISO timestamp with offset), ``year``, ``month``, ``day``, ``hour``,
``minute``, ``second`` and ``offset``. Every field also has a ``date.utc`` form.
Numeric date components are strings with leading zeros. Combine them for a
custom format::

   # config/ptk/project.ptk.yml
   vars:
     archive: build_${date.timestamp}.zip
     day_folder: ${date.year}/${date.month}/${date.day}
     utc_stamp: ${date.utc.year}-${date.utc.month}-${date.utc.day}_${date.utc.hour}${date.utc.minute}

   # config/ptk/jobs/show-date.ptk.yml
   steps:
   - show:
       uses: echo
       with:
         message: ${vars.archive}

The captured local and UTC values are recorded under ``context.date`` in run
reports. A new invocation captures a new instant; a dry run previews its own
instant. Minute-level timestamps are not unique run identifiers: include a run
ID when distinct runs need distinct destinations. Local time depends on the
machine; use ``date.utc`` for a common timezone across developer and CI machines.

Jobs and parameters
----------------------

PTK calls executable units **jobs**. Use ``jobs:`` for definitions,
``project.default_job`` for the default, and ``job:`` for a workflow call.
For example::

   # config/ptk/project.ptk.yml
   name: demo
   default_job: check

   # config/ptk/jobs/check.ptk.yml
   steps:
   - greeting:
       uses: echo
       with:
         message: Running ${run.job}

   # config/ptk/workflows/verify.ptk.yml
   steps:
   - checks:
       job: check

Job declarations
~~~~~~~~~~~~~~~~

Job names use lowercase letters, digits and hyphens, starting with a letter.
Parameters use lowercase letters, digits and underscores. Built-in command and
option names are reserved. A job needs at least one step. The default job
must exist and be available to ordinary users.

Parameters become CLI options: ``build_type`` becomes ``--build-type``;
boolean options get positive and negative forms. Precedence is explicit CLI
value, parameter file, declared environment variable, then default.
A required parameter cannot also have a default. Choice parameters need choices.
Defaults may refer to variables, environment or variant data, but not other
parameters. Validate them for each concrete variant you support.

Steps and execution
-------------------

Steps are an ordered list of single-key mappings, for example::

   # config/ptk/jobs/build.ptk.yml
   steps:
   - check:
       run:
       - check.py
       python:
         interpreter: cli

Each step has exactly one of ``run``, ``uses`` or nested ``steps``.
Names must be unique within their set. ``parallel`` applies only to sets;
``python`` and ``passthrough`` apply to command steps; ``with`` applies to
``uses``. Prefer argument lists for paths containing spaces and user-supplied
parameters. String commands use platform shell syntax.

The registered built-ins are ``echo``, ``wait``, ``report.import``,
``configs.sync``, ``tools.ensure``, ``files.copy``, ``files.clean`` and
``variant.generate`` and ``version.generate``. Their contracts are in :doc:`/reference/plugins`.
``--from`` and ``--to`` select top-level steps.

Python modes are mutually exclusive: ``uvx`` for a Python tool, ``venv`` for
cached requirements/packages, ``project`` for a uv project, or
``interpreter: cli`` for ptk's interpreter. Pin tool versions in reproducible
project configurations. ``python: {project: ., groups: [docs]}`` adds dependency
groups from that project's ``pyproject.toml`` to the uv run. ``groups`` is only
valid with ``project`` mode; the normal uv default groups still apply.
Dry runs describe runtimes without creating them.

Substitution and conditions
---------------------------

Use ``${vars.name}``, ``${params.name}``, ``${env:NAME}``,
``${env:NAME:-fallback}``, ``${project.root}``, ``${vh.variant}``,
``${vh.features.FEATURE}``, ``${vh.data.name}``, and run paths such as
``${run.build_dir}``. Escape literal substitutions with ``$${...}``.
Unknown references are errors. The run paths are per step where applicable.

The configuration editor offers **Insert variable…** and completion after
``${`` in template-capable text fields. Its catalogue and field capabilities
come from the installed PTK via ``describe --json --configuration``. That
catalogue contains names, descriptions, context restrictions and availability
notes, never resolved environment or credential values. Literal fields such as
project names, plugin names and file discovery paths do not offer interpolation.
Job parameter defaults exclude ``params.*`` and ``run.*``. Credential and secret
parameter references are offered only in step environment values; ``github.*``
is restricted to Artifactory destination templates.

``when`` uses the safe expression evaluator, not Python execution. Feature names,
``COMPONENT_*`` flags, ``variant``, ``os``, ``ci`` and supported namespaces can
be used. Check the resolved values with ``variant show`` and ``variant explain``.
Variants can inherit through ``extends``, carry aliases and free-form ``data``,
and mark common parents ``abstract: true``.

Credentials
-----------

Declare credential fields and provider order under ``credentials``. The default
chain is env, keyring, gopass, vault, prompt. Keyring is optional; prompting is
unavailable in CI. Supply secrets to individual steps using::

   secrets: {TOKEN: service.token}

Never interpolate secrets into command arguments, URLs or shared config files.
A shell command that expands a secret environment variable into an argument
still exposes that secret in the child's command line. Have the child program
read its environment directly. Use ``self-service creds setup``, ``self-service creds list``, and
``self-service creds set NAME FIELD`` to diagnose or provision values. Do not include real
credentials in examples, fixtures or documentation.

Tools, configs and outputs
--------------------------

Declare tool version checks under ``tools`` and reference them in a job's
``requires_tools``. Missing tools block real execution. Preview installation
with ``ptk self-service tools --dry-run``. System package managers require ``--allow-system``;
Chocolatey bootstrap is explicit. Prefer checksummed downloads.

Only entries under ``configs`` are managed. Preview ``ptk maintainer sync configs --diff``;
commit generated files and enforce ``ptk validate --generated`` in CI. Ruff uses a generated
``ruff-base.toml`` and a project-owned ``ruff.toml`` extending it.

Local Git hooks
~~~~~~~~~~~~~~~

Enable automatic pre-commit hook installation in ``configs.ptk.yml`` inside your configuration
folder, for example ``config/ptk/configs.ptk.yml``::

   # config/ptk/configs.ptk.yml
   pre-commit:
     enabled: true

A maintainer runs ``ptk maintainer sync configs pre-commit`` and commits the generated
``.pre-commit-config.yaml``. An optional ``output`` changes its location. Ordinary
job execution never generates or rewrites this configuration. If it is missing,
startup fails with instructions to ask a maintainer to synchronize it.

Before a local job runs, PTK checks the configured hooks and installs or repairs
them when necessary. This is available to every developer, including
non-maintainers. A local workflow checks each participating repository once,
before starting any sequential or parallel jobs. Unrelated VMR repositories are
not inspected. Missing/disabled ``configs.pre-commit`` entries, help, dry runs and
CX/CI job execution do not install hooks. ``self-service hooks install`` uses the same installer;
``self-service doctor`` reports hook status without installing anything.

Detection uses Git's repository/common-directory queries, supporting ordinary
checkouts, ``.git`` symlinks, ``gitdir:`` pointer files and linked worktrees. PTK
checks the generated hook, its configured file and its executable Python runtime,
including whether that interpreter can actually import pre-commit. A usable
existing installation is kept without package installation. Hook changes are
serialized across PTK processes sharing a Git directory.

When installation is needed, uv creates a dedicated environment at
``<git-common-dir>/ptk/pre-commit`` using PTK's Python interpreter and installs
``pre-commit>=4,<5`` through the configured uv package indexes. The environment is
reused, independent of job environments and uv's disposable tool cache. Hook
tool versions still come from the generated configuration's ``rev`` fields.
All ``default_install_hook_types`` are installed (default: ``pre-commit``).
The first Git commit may download the individual hook environments; PTK startup
installs hook scripts but does not run linting or download every hook's tools.

Existing ordinary hooks are preserved by pre-commit's migration mode as
``<hook>.legacy`` and still run. PTK refuses a collision with an existing backup,
hook-file symlinks, and a configured ``core.hooksPath``; it does not overwrite or
unset these configurations. Resolve such conflicts with the repository's
maintainer. Installation, validation or verification failures stop the job or
workflow before its first step. Linked worktrees share hooks and should use the
same relative pre-commit configuration path and installed hook types.

Use ``ptk self-service hooks install|uninstall|status`` for explicit hook management,
``ptk pre-commit run`` for staged files and ``ptk pre-commit run --all-files`` for all tracked
files. ``ptk pre-commit validate`` checks the hook configuration. These commands
honor a custom ``configs.pre-commit.output`` and also work when automatic
installation is disabled. See :doc:`/reference/cli` for file/ref selection and exit codes.

PTK's pre-commit commands remove inherited Python environment selectors such as
``VIRTUAL_ENV``, ``UV_PROJECT_ENVIRONMENT``, ``UV_PYTHON`` and pip/uv installation
targets. They also remove PTK's own virtual-environment bin directory from the
hook PATH. A ``language: system`` hook must select its project environment
explicitly (for example, ``uv run --project .``); it must not synchronize PTK's
installation. Package-index, proxy, certificate and cache settings are retained.
The dedicated pre-commit interpreter does not by itself isolate the environments
used by hook subprocesses. Hooks launched directly by Git or pre-commit retain
that launcher's environment; explicit paths in hook commands remain the author's
responsibility.

If a previous hook removed PTK, pull the fixed checkout and rerun
``install/install.ps1`` on Windows or ``sh install/install.sh`` on Linux.
Then check ``ptk --version`` and refresh the Project Toolkit extension.

Automatic installation prevents forgotten setup. It cannot prevent deliberate
local bypass such as ``git commit --no-verify``. Run ``ptk pre-commit run --all-files`` in CI
and require that check through GitHub branch protection/rulesets.
``ptk validate --generated`` verifies generated configuration freshness without
maintenance permissions; it does not execute hooks. Generating shared files
requires ``ptk maintainer sync configs``.

Build and report outputs
~~~~~~~~~~~~~~~~~~~~~~~~

The layout defaults to ``_builds``, ``_bin``, ``_logs`` and ``_reports``.
Write test results into ``PTK_STEP_REPORTS_DIR``. JUnit, SARIF and Cobertura
are imported into configured JSON, HTML, JUnit, Markdown or GitHub reports.
``report export`` regenerates reports from stored runs. Use log files and
``events.jsonl`` when diagnosing failed or skipped steps.

Report summaries
----------------

HTML reports start with the recorded PTK/project versions, repository alias,
selected variant description, inheritance, active components and feature values.
Declared tool dependencies show detected versions and their resolved check
executable paths in the command environment. Unknown versions/sources are labeled
explicitly; configured download URLs are not presented as proven installation
sources. This is a snapshot of declared tools, not a transitive Python package inventory.
Multiple tool versions/sources observed during a run are retained.

This context is saved with the run, so exporting an older report does not replace
its versions or variant settings with the current configuration. Older runs without
this data show "Not recorded". JSON, Markdown/GitHub summaries and JUnit properties
also carry recorded context.

The Tests section and each test suite have summary cards for executed, passed,
skipped and failed cases. Executed excludes skipped cases; failed includes both
assertion failures and test errors (for example, fixture/setup errors). Detailed
case rows retain the distinction between failures and errors. Step counts remain
separate from test-case counts. Cards use green for passed, red for failed, gray
for skipped, blue for general information and amber for warning findings. Error
findings use red. Colors adapt to light/dark mode; text labels always identify
the meaning independently of color.

Jobs can open their HTML report automatically after a local run::

   # config/ptk/jobs/test.ptk.yml
   open_report: on_errors
   steps:
   - pytest:
       python:
         project: .
       run:
       - python
       - -m
       - pytest

``always`` opens after every executed run. ``on_errors`` opens for failed jobs
or steps (including tolerated failures), failed/error test cases, error-level
findings, or report import problems. Warnings, skipped results and cancellation
alone do not trigger ``on_errors``. This does not change the job's exit code.
When enabled locally, HTML is added to the configured report formats, even when
``report_formats`` is empty. A missing browser prints a hint and keeps the
report available on disk. Failed report generation never opens an old report.

Automatic opening is disabled in CX/CI mode (including ``--ci``), and dry runs
neither generate nor open reports. Multi-variant runs apply the policy separately
to each variant. VMR jobs use the owning repository's configuration. Manual
``ptk report open`` remains available regardless of the job policy.

Every HTML table has a case-insensitive substring filter for each column. Filters
combine across columns, operate locally/offline, and show the remaining row count.
Clear a filter to restore rows. Filtering does not change recorded totals or cards.

Maintainer visibility and current limits
----------------------------------------

Put ``maintainers.ptk.yml`` directly in ``repository.config_path``. Its schema is
a list of login IDs, without name/email/user objects::

   maintainers:
     - alice
     - bob

Locally PTK compares the OS login name with this list, case-insensitively. On
GitHub Actions it uses ``GITHUB_TRIGGERING_ACTOR`` (the user starting a rerun),
falling back to ``GITHUB_ACTOR``. Other CI systems use the OS login name. Git
author names and email addresses do not grant maintainer status. Add both login
IDs when someone's local and GitHub usernames differ. ``ptk self-service doctor`` shows
the detected user ID, role and identity-file path.

Missing/empty lists grant no maintainer rights; malformed lists are configuration
errors. ``PTK_ROLE=user`` can reduce a listed maintainer's visibility for testing.
``PTK_ROLE=maintainer`` no longer elevates anyone. Upgrade old entries such as
``- {name: Alice, email: alice@example.com, user: alice}`` to ``- alice``.

The ``maintainer`` group contains configuration inspection/schema export,
shared configuration and editor generation, version discovery/snapshot generation,
artifact destinations, and all jobs/workflows declared ``audience: maintainer``.
These commands require a listed maintainer, including their ``--check``,
``--diff`` and ``--dry-run`` modes. ``command_audience: all`` cannot relax this
restriction. Invalid project configuration does not expose maintenance commands.
The global ``--ci`` / ``--no-ci`` option is also maintainer-only. Automatic CI
detection remains available without either switch.

Ordinary users retain tool installation, personal credential management,
diagnostics, validation, reports and everyday jobs/workflows. ``ptk validate``
is always available, even when configured policies restrict other commands.
Use ``ptk validate --generated`` in CI to check shared configuration freshness
without granting maintenance privileges. ``command_audience`` can restrict
additional commands using their canonical paths, such as ``self-service.creds``.
Developers select variants
for a run with global ``-V NAME`` before the command. The variant CLI only
inspects configuration; modify YAML directly to change definitions.
``init`` remains available for unconfigured repositories, lists the creator
as their initial maintainer, and refuses to overwrite existing configuration.
In VMR initialization, configured repositories continue to be skipped.

A job or workflow with ``audience: maintainer`` is likewise hidden and refused
for normal users; maintainer jobs/workflows are excluded from user editor tasks.
Use ``maintainer sync tasks --users-only`` as a maintainer when committing shared
tasks. For VMR workspace-level editor commands and workspace-owned restricted
workflows, place a separate ``maintainers.ptk.yml`` at the VMR root. Workspace
membership grants no privileges in member repositories, or vice versa. Workspace synchronization preflights permissions for every member before writing anything.

These checks protect ordinary CLI use, not against someone editing their own
checkout or process environment. Repository configuration and plugins remain
trusted code; enforce release permissions and credentials in CI separately.

Variant inspection, matrix runs and the command structure are described in :doc:`/reference/cli`.
The installed plugin interfaces, generators and built-in command visibility are
covered in :doc:`/reference/plugins`. Background process limitations are in :doc:`/reference/execution`.


Additional execution controls
-----------------------------

``path`` parameters accept paths containing spaces. ``secret`` parameters use
``env:`` or a hidden prompt requested with ``--PARAM`` (without a value).
They have no literal defaults, are masked in run metadata, are not exported as
``PTK_PARAM_*``, and may be substituted only in step ``env``. Prefer credential
providers for reusable credentials. Never pass secret values as CLI arguments.

``report: false`` excludes a step and its descendants from exported reports and
tool-result imports; audit logs and the overall failure status remain complete.
Groups and built-ins support retries and deadlines. A group deadline cancels its
children, without cancelling unrelated groups. Repeating a group repeats all of
its children, so enable retries only for repeatable work. Built-in/plugin Python
handlers must cooperate with ``ctx.cancel.is_set()``; Python threads cannot safely
be forcibly terminated. ``wait`` cooperates with deadlines and Ctrl+C.

Shared defaults and tool files
------------------------------

Declare shared tools in ``tools.ptk.yml``. Put global ``requires_tools`` and
``param_defaults`` in ``project.ptk.yml``, and job-specific settings in that job's
file. Each document owns its fields. Shared defaults are applied after loading;
job requirements can override or disable individual tools without changing shared
tool definitions. GitHub Actions is recognized automatically; maintainers can
inspect either execution mode with ``--ci`` / ``--no-ci``.

Global ``param_defaults`` supplies defaults only to parameters that a job
explicitly declares. Job-specific ``default`` values take precedence. An
explicit ``default: null`` opts out; ``required: true`` parameters remain required.
Inherited values are validated against each parameter's type/choices, and
``config show --sources`` retains the global value's source location::

   # config/ptk/project.ptk.yml
   param_defaults:
     jobs: 8

   # config/ptk/jobs/build.ptk.yml
   params:
     jobs:
       type: int
   steps:
   - compile:
       run:
       - cmake
       - --build
       - build
       - -j
       - ${params.jobs}

Tool requirements merge **per tool**, not by replacing the entire list::

   # config/ptk/project.ptk.yml
   requires_tools:
   - git
   - cmake

   # config/ptk/tools.ptk.yml
   git:
     check: git --version
   cmake:
     version: '>=3.28'
     check: cmake --version
     choco: cmake
   ninja:
     check: ninja --version

   # config/ptk/jobs/build.ptk.yml
   requires_tools:
     cmake:
       version: '>=3.30'
     ninja: true

``build`` requires git, cmake and ninja, with its own CMake version constraint.
Other jobs retain the global requirements and CMake definition. Use
``git: false`` to disable only git for one job. ``requires_tools: []`` or ``{}``
changes nothing; a job's unmentioned global requirements remain inherited.
List shorthand enables/adds named tools; mappings can enable, disable or override
a named tool's settings. All referenced names must be declared under ``tools``.

``self-service tools --job build`` uses that job's effective tool settings.
Selecting jobs that require conflicting settings for the same tool fails
before installation; install for those jobs separately. Without ``--job``,
``self-service tools`` uses global requirements when supplied, otherwise all declared
tools. Declaring a tool alone does not make it a requirement of every job.

Isolated job environments
----------------------------

``environment.isolate`` defaults to true. Each job receives a new environment
containing OS essentials, explicitly kept variables, configured values and its
selected managed tools. ``inherit_path`` defaults to false: PATH starts with
standard OS directories, not the caller's potentially repository-specific PATH.
This is environment isolation, not a filesystem or process sandbox::

   # config/ptk/project.ptk.yml
   environment:
     isolate: true
     inherit_path: false
     keep:
     - HTTP_PROXY
     - HTTPS_PROXY
     set:
       BUILD_MODE: reproducible

   # config/ptk/jobs/build.ptk.yml
   environment:
     keep:
     - HTTP_PROXY
     - HTTPS_PROXY
     - COMPANY_SDK
   steps:
   - compile:
       run:
       - compiler
       - source.c

A job's explicitly set environment fields override the global fields.
Lists replace, so include all desired ``keep`` entries in a job override.
``isolate: false`` deliberately inherits ordinary host variables;
``inherit_path: true`` separately opts into caller PATH. Step ``env`` and secrets
are applied to that command only. Neither the host process nor another job's
environment is mutated. Tool versions are rechecked in the final subprocess
environment, including Python-runtime and step overrides.

Managed downloads and Python tools are stored by tool name and effective
version/source identity. Only installations selected by the job's effective
requirements (or its explicit ``tools.ensure`` selections) enter its PATH.
A later ``tool: true`` keeps earlier settings; ``tool: false`` disables that
requirement. System binaries on the OS path are version-checked. Chocolatey,
apt/dnf and custom plugin installers are shared host operations and cannot
provide the same side-by-side isolation. Prefer managed downloads or Python
tools for incompatible repository versions. Host PATH entries pointing into
PTK's managed cache are removed before the selected installations are added.

The complete ``examples/authoring`` starter is exercised by the skill tests.

Version discovery is documented in :doc:`/guides/versioning`. It uses a maintained
``versioning.ptk.yml`` and ignored per-run ``.gen.version.ptk.yml`` snapshots.

Toolbase and Artifactory sources
========================================

These sources participate in ``ptk self-service tools``, ``--setup`` and
``tools.ensure``. Job-level ``requires_tools`` overrides and VMR repository
selection work as for other tools. Source order is custom installers, Toolbase
(Windows), Artifactory, Chocolatey (Windows), uv, download, then opt-in apt/dnf.

Toolbase-only tools are ignored on Linux: they do not trigger version checks or
installation failures. If a tool also declares a Linux-compatible source, that
source remains active.

Toolbase must already be installed on Windows, with ``TB_HOMEDIR`` set and
``tbexcmd`` / ``TBUpdate`` available on the caller's PATH::

   # config/ptk/tools.ptk.yml
   ninja:
     version: ==1.12.1
     toolbase:
       package: ninja
       version: 1.12.1
       environment: ptk
       bin:
       - bin

PTK enables the exact ``package/version`` and runs ``TBUpdate -e`` only if that
version's directory is missing. Nonzero exits fail installation. Enable/update
is serialized across PTK processes sharing the tools directory. ``bin`` lists
relative executable directories (default ``[.]``); for Python, configure
``[., Scripts]`` explicitly. Only those directories enter the selected job's
PATH. Inherited paths below ``TB_HOMEDIR`` are removed before activation. PTK
writes neither global PATH nor ``GITHUB_ENV`` nor a shared ``.env`` file.
Toolbase itself controls its installation location and update side effects.
Validate this integration with your local Toolbase environment; it is not
exercised by PTK's pytest suite.

Artifactory uses an installed ``curl`` executable, HTTPS and a bearer token from
an optional environment variable. No JFrog CLI or legacy downloader is required::

   # config/ptk/tools.ptk.yml
   compiler:
     version: ==12.3.0
     check: compiler --version
     artifactory:
       url: https://artifacts.example.org/artifactory
       repository: tools-local
       path: compilers/windows
       name: compiler-12.3.0.zip
       sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
       token_env: ARTIFACTORY_TOKEN
       bin: bin

``url`` is the Artifactory base URL, not the repository URL. ``path`` defaults
to ``.`` (repository root). ``artifactory`` may also map ``windows`` and ``linux``
to separate source definitions. No token values belong in YAML. The token must
be available in PTK's caller environment when setup runs; setup does not prompt
for or resolve credential-provider entries. curl receives it through a temporary
configuration file, removed after the request, rather than command arguments.
TLS certificate verification remains enabled; curl's normal CA/proxy environment
settings apply. HTTP failures, timeouts and checksum mismatches fail installation.

For property or wildcard selection, replace the exact selection with::

   path: ZippedTools/compiler
   name: compiler_12.3.0*.zip
   properties:
     rb_version: "12.3.0"
   select: unique

PTK queries Artifactory AQL. Property values match exactly; ``path`` and ``name``
support AQL wildcard patterns. The default ``unique`` rejects multiple matches.
``select: latest`` explicitly chooses the newest creation timestamp, with stable
path/name tie-breaking. This is not semantic-version sorting. AQL's SHA-256 is
used when ``sha256`` is not configured; without either, installation fails.
Exact URL downloads require an explicit checksum.

ZIP and tar archives use PTK's existing extraction support. Standalone files use
``extract: false``. Convert legacy 7z bundles to ZIP/tar before using this source.
Downloads are checksum-verified before entering the managed tools directory;
failed downloads do not create an installation marker. Downloads are cached by
the effective tool definition, so ``latest`` is resolved only on installation,
not refreshed on every job. Pin properties/path/checksum for reproducibility.
Changing a source or version creates a distinct installation, and each job
activates only its selected tool definitions. No corporate hostnames, legacy
runtime filters or repository-specific download layout rules are built in.

Disabling installation in Docker
================================

Set ``docker: false`` on a tool to disable its installation inside Docker::

   # config/ptk/tools.ptk.yml
   compiler:
     docker: false
     version: '>=12'
     check: compiler --version
     apt: gcc

The default is ``docker: false``: tools must normally be supplied by the image.
Set ``docker: true`` on a tool to allow PTK to install it inside Docker. With ``false``,
PTK still checks the tool and its version, includes it in reports, and activates
any existing managed installation. Only installation is blocked, including
``self-service tools``, ``--setup`` and ``tools.ensure``. A missing or incompatible
tool remains an error; PTK explains that installation is disabled in Docker.
Prepare the required tool in the image or mount an existing managed cache.
If using an image tool outside the default OS PATH, add its directory to the
job's environment configuration. No Docker daemon or Docker CLI is needed.

Job-level ``requires_tools`` can override ``docker`` like other tool settings.
Changing this policy does not change the managed installation identity.
Detection checks ``/.dockerenv``, Docker cgroup markers and ``container=docker``.
These signals are best-effort, especially for Windows containers or unusual
container runtimes. Set ``PTK_DOCKER=1`` explicitly in those images; use
``PTK_DOCKER=0`` to override automatic detection. Having Docker installed on the
host does not count as running inside Docker.

Local orchestration
===================

Use ``workflows/<name>.ptk.yml`` to compose existing jobs into local sequential and
parallel groups, including jobs from configured VMR members. Workflows load
from the repository configuration directory; VMR roots can also own a workflow
file. See :doc:`/guides/workflows` for complete syntax, command examples, preflight,
reports, VS Code tasks and the explicit local-only execution boundary.

Output folder configuration
---------------------------

Place ``folder_structure.ptk.yml`` in each repository's ``repository.config_path``::

   # config/ptk/folder_structure.ptk.yml
   builds: _builds
   bin: _bin
   logs: _logs
   reports: _reports

PTK discovers this file automatically. Define each layout field in one file;
duplicate definitions are errors.
Absent this file, these four PTK defaults apply; there is no VMR-level inheritance.
Folder values are plain directory names. ``layout.root`` defaults to the repository
root; cleanup requires its output directories to remain inside the repository.
The report folder selected by ``layout.reports`` is included in cleanup.

All four categories use ``<variant>/<job>`` beneath their configured directory.
Without variants, the variant directory is ``default``. This keeps selected-job
cleanup from deleting another job's binaries. ``ptk init`` generates the
folder configuration file for new repositories.

Execution filters
-----------------

Jobs and job steps accept ``only_cx: true``, ``only_variants: [debug, release]`` and
``omit_variants: [debug]``. ``only_cx`` hides a job outside CX/CI, including the
extension inventory, and explicit execution is rejected. Job variant restrictions
return an error. At step level, these filters skip the step (and nested children).
They never select a variant. Variant filters match resolved concrete names;
``default`` represents repositories without variants.
