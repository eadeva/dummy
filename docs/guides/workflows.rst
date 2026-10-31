Local job workflows
======================

Workflows orchestrate existing PTK jobs **on the developer's machine**. They
require neither GitHub nor a CX runner. Run one from the terminal or a generated
VS Code task. Each job keeps its repository, variant, tool requirements,
credentials, environment, maintainers and ordinary logs/reports.

Workflow, job and step
----------------------

The names deliberately follow GitHub Actions terminology. PTK uses three
levels: a **workflow** coordinates reusable jobs; a **job** defines a runnable
task; a **step** invokes a command, script or built-in operation inside
that job. A job can run directly, without belonging to a workflow.

A workflow's ``jobs`` mapping contains named job invocations and their ``needs``
dependencies. A job's ``steps`` mapping contains named executable steps with
its own ``needs`` edges. Dependencies stay within their respective scopes. See :doc:`/reference/execution` for job-step selection.

For example, ``verify`` can call ``build`` and then ``test``. The ``build`` job
can contain ``configure`` and ``compile`` steps that call the chosen build tool.
Keep tool commands in the job and reuse that job from workflows or CX pipelines.
See :doc:`configuration` for job and step fields and
:doc:`/architecture/06-runtime-view` for execution behavior.

Local orchestration and CX pipelines
------------------------------------

``ptk workflow run`` refuses CX mode, whether detected or forced with ``--ci``.
``list``, ``show`` and ``dry-run`` are inspection operations and remain available.
GitHub template generation and a generic PTK GitHub Action for those workflows
are draft proposals; neither is implemented by this feature. The familiar
terminology does not imply that PTK YAML is interchangeable with GitHub Actions
YAML or that local workflows are executed by a CX runner.

Files and commands
------------------

Put each workflow in ``workflows/<name>.ptk.yml`` under ``repository.config_path``.
The file contains the workflow body, without a ``workflows`` wrapper. Names use
lowercase letters, digits, underscores and hyphens, starting with a letter.
Workflows and jobs have separate namespaces::

   ptk workflow list
   ptk workflow show verify
   ptk workflow run --dry-run verify
   ptk workflow run verify
   ptk verify

Workflow shortcuts appear alongside jobs in ``ptk --help``. If a job and
workflow share a name, the local terminal prompts for ``job`` or ``workflow``.
CX selects the job without prompting. Non-interactive local callers must use
``ptk run verify`` or ``ptk workflow run verify`` explicitly. Help never prompts.
Built-in commands and VMR repository aliases retain priority over shortcuts;
such workflows remain accessible through ``workflow run``.

A complete repository-owned workflow:

.. literalinclude:: ../../examples/workflows/app/config/workflows/verify.ptk.yml
   :language: yaml

The example lives in a small manual VMR. From ``examples/workflows`` run::

   ptk workflow list
   ptk workflow run frontend/all
   ptk workflow run frontend/verify
   ptk frontend workflow run verify
   ptk frontend/verify
   ptk frontend verify

Copy the example to a temporary folder before trying it if you want to preserve
the documentation tree. Its jobs use portable built-ins, without compilers,
network access or credentials.

Job invocations and dependencies
--------------------------------

``jobs`` is a nonempty mapping from unique invocation IDs to job calls. Each ID
starts with a letter or digit and can contain letters, digits, underscores,
hyphens and dots. It identifies one invocation within this workflow, independently
of the target job name. For example::

   jobs:
     compile:
       job: my_repo:build
     unit:
       job: my_repo:test
       needs: compile
       params:
         suite: unit
     integration:
       job: backend:test
       needs: compile
     package:
       job: my_repo:package
       needs: [unit, integration]

``compile`` runs first; ``unit`` and ``integration`` can run concurrently;
``package`` starts after both succeed. ``needs`` references invocation IDs, never
repository aliases or target job names. Each repository/job pair may appear once
per workflow. Different repositories may expose jobs with the same name.

Each invocation accepts:

* ``job``: an existing job name in the owner's repository, or ``REPO:JOB``.
  Workspace-owned workflows require the qualified form.
* ``needs``: one invocation ID or a list of IDs. Omission or ``[]`` makes the job
  immediately eligible. All listed prerequisites must complete successfully.
* ``params``: values for parameters already declared by the target job.
  Values use that job's types, choices and validation. Secret parameters are
  not configurable in a workflow; keep secrets in the target job's credential
  declarations.
* ``continue_on_error``: default false. Tolerate this invocation's failure for
  dependency scheduling and exit status; its report still records the failure.

YAML order controls presentation, not execution. Ready jobs run as workers become
available. A completed job releases its dependents without waiting for unrelated
branches. There are no workflow ``steps``, nested groups, ``parallel`` or ``repo``
fields.

Workflow invocations call jobs, never other workflows or arbitrary shell commands.
Put commands, retries, step timeouts, skip filters and cleanup inside the target job.

The workflow accepts ``help``, ``audience: all|maintainer``, ``open_report``, ``jobs``
and ``max_workers`` (default 4, range 1–32). This limit applies to active **job
calls**, not to parallel steps inside those jobs. Each repository retains its own
environment, tool configuration and credentials. Job parameter defaults, version
discovery and ``requires_tools`` overrides continue to apply.

Failure, preflight and isolation
--------------------------------

Each repository/job pair can be chosen only once in a workflow, including calls
with different parameters. An unqualified local target and its owner-qualified
form identify the same job. The same job name in another repository is distinct;
the same job may still participate in different workflows.

Loading rejects duplicate job targets, unknown dependencies, repeated dependencies, self-dependencies and
cycles; cycle errors show the dependency path. PTK prepares every job before
starting the first. Unknown repositories/jobs,
invalid parameters/variants, unsatisfied declared tool/credential requirements
and maintainer restrictions fail the preflight. Credentials are resolved serially before parallel execution,
so there are no concurrent credential prompts. Each call gets its own application
and prepared run. Versions are discovered during this preflight and retained for
that call; a previous job changing Git state does not refresh later snapshots.

A dry run resolves configuration and plans the calls, but creates no run outputs,
installs no tools and does not resolve credentials. As with job previews,
custom version-discovery commands can execute and must be read-only. Workflow
previews list invocation IDs, resolved targets and prerequisites (or ``ready``); use the target job's ``dry-run`` to
inspect its individual commands.

A failed or skipped prerequisite blocks dependent jobs, which are recorded as
skipped with the prerequisite IDs and statuses. Independent branches continue.
``continue_on_error`` allows dependents to run after a failed invocation, and
preserves that failure in reports. It does not tolerate skipped or cancelled jobs.
Ctrl+C propagates cancellation to active job runners and prevents pending calls
from starting.
The workflow returns exit code 0 for success/tolerated failures, 1 for job
failure and 130 for cancellation. Preflight/configuration errors use exit code 2.

Jobs with no direct or transitive dependency ordering may not share the same repository/job/variant output folders.
They also may not share a ``python.project`` environment, since uv can synchronize
that project's shared virtual environment while another job is using it.
For parallel jobs in one project, set a distinct absolute
``env.UV_PROJECT_ENVIRONMENT`` on each job, for example
``${project.root}/.ptk/venvs/package``. PTK checks the resolved environment paths,
including step-level overrides. This check applies even with ``max_workers: 1``;
express resource ordering with ``needs`` rather than relying on worker limits.
Use absolute paths for uv workspace members so
the environment location does not depend on uv's workspace-root discovery.
PTK's own ``verify`` workflow runs ``check``, ``test`` and ``package`` sequentially,
alongside ``docs``; these jobs have separate environments. Existing job locks
also protect against a separate PTK invocation using the same output folders.
PTK cannot infer arbitrary paths or external resources used by scripts: authors
must add dependencies between jobs that write the same files, hardware device or service.

This division of responsibility deliberately preserves project flexibility:
projects choose their scripts, build tools, artifact contracts and execution
policies. **The project implementation is responsible** for its input/output
checks, shared-resource coordination, safe retries and recovery, and any required
isolation. PTK orchestrates the declared calls and uses the outcomes they report.
It does not inspect or control arbitrary internal operations of project scripts.

The orchestration checks do not sandbox jobs or establish a general input/output contract.
A workflow edge orders job calls; it does not copy artifacts, verify required
files or guarantee that a successful producer created valid outputs. Commands
run with the user's permissions and can access paths outside their configured
folders. Project implementations validate artifacts and coordinate other shared resources;
worker limits and known-conflict checks do not provide general mutual exclusion.
See :ref:`execution-boundaries` for the full responsibility table and the limits
of retries, cancellation, cleanup and partial runs.

Tool selection remains per job. Toolbase-only definitions are ignored outside
Windows; Docker installation policy still applies. Workflow preflight expects
declared tools already available unless a job handles its own checks through
``tools.ensure``. There is no workflow-wide installer. Install under the target
repository/job before the run.

VMR ownership
-------------

At the VMR root, ``workflows/<name>.ptk.yml`` holds each workspace workflow.
Each document contains one workflow body. Every workspace-owned invocation must use
``job: REPO:JOB``. Only configured VMR members can be referenced; filesystem paths are not
repository selectors.

Workspace-owned workflows have no variant configuration. They can call repositories
without variants; workflows involving variant-enabled repositories must be owned by
a repository with the required mappings. For example, use ``frontend/all``.

Workspace-owned names are unqualified, for example ``all``. Member-owned names
are qualified, for example ``frontend/verify``; identical names in different
repositories never merge. Under ``ptk frontend workflow``, use the local name
``verify``. Manual VMR members should be invoked from the workspace root to retain
membership context. Use ``ptk frontend verify`` from that root to select the
member's command surface. Git-pointer membership is detected automatically
when invoking PTK inside a member directory.

An owner workflow's ``audience`` and ``command_audience.workflow`` policy are
checked along with the target job's actual repository role. A public workflow
cannot bypass a maintainer-only job. Workspace-owned maintainer workflows
use the login-ID list in ``maintainers.ptk.yml`` at the VMR root;
member job roles still use their own repository settings. Neither scope grants
rights in the other. ``PTK_ROLE=maintainer`` does not elevate a user. These role policies
remain a developer convenience, not an operating-system security boundary.

Reports and editor tasks
------------------------

Each job writes its normal reports and applies its ``open_report`` policy.
The workflow also writes an immutable summary and child HTML/JSON reports under::

   _reports/workflows/NAME/RUN-ID/workflow.json
   _reports/workflows/NAME/RUN-ID/workflow.html
   _reports/workflows/NAME/RUN-ID/workflow.log
   _reports/workflows/NAME/RUN-ID/jobs/INVOCATION-ID/report.html

Repository-owned workflows honor the owner's layout/report directory; workspace
workflows use the workspace's ``_reports``. Child report snapshots include their
own log copies so later runs do not redirect earlier report links to newer logs. Workflow reports use the same overview, failure recap, execution details,
diagnostics and configuration sections as job reports. Execution entries show
invocation IDs, ``needs``, targets, status and skip reasons. Graph jobs expand
to show their recorded steps and internal edges without changing job dependencies.
See :doc:`reports` for navigation, filtering and evidence handling.
The JSON summary retains job results in ``jobs``, child report snapshots in
``children`` and the nested dependency projection in ``graph``.
It also records ``owner_variant`` so reopened report links retain the saved
workflow's variant. Report-link lines use the same owner prefix and entity
color as the run headers, including qualified child job names.
Open a child report for its project versions, tool dependencies and test details.
Workflow history is retained until explicitly removed; it has no automatic rotation.

``workflow.log`` is a timestamped plain-text transcript written as child jobs
run, including workflow/job/step boundaries, metadata and final status counts.
The console uses purple workflow headers, cyan job headers and blue step
headers. It lists participating repositories' already prepared versions and
variants; it does not perform another version lookup just for display. Workspace
and cross-repository workflows qualify step prefixes as
``[variant][repository:job][step]``. Header blocks stay together while output
from parallel jobs can alternate between them. Each summary is also one block:
job summaries list steps, and the workflow summary lists job identities,
variants, invocation aliases, outcomes, durations and skip reasons. The
``What failed`` recap retains exact step identities and annotates allowed
failures even when the workflow passes. Workspace headers identify their scope
as ``[workspace][workflow]`` instead of inventing a shared variant; each job
row shows its actual variant. Individual raw step logs remain
available through the child reports. See :doc:`log-analysis` for metadata,
verbosity and formatting details.

Use ``ptk report open --workflow NAME`` to reopen the latest saved aggregate HTML report.
At a VMR root, use a workspace workflow name or qualify a member workflow as
``ALIAS/NAME``. The extension's report icon uses this operation. Add
``--if-exists`` to print an informational message instead of failing when no
report is available. Opening a saved report does not execute workflow jobs.

The workflow opens its summary HTML report automatically after a local run.
Set the policy on the workflow, independently of each job's report policy::

   # config/ptk/workflows/verify.ptk.yml
   open_report: always
   jobs:
     check:
       job: check
     test:
       job: test
       needs: check

Every workflow also writes ``diagnostics.html`` with findings from all children.
Local workflows with active errors always open that aggregate diagnostics report,
including with ``open_report: null``. Active errors include failed job calls,
tolerated failures, unsuppressed imported errors and collection problems.
Warnings, ignored/justified imported findings, skips and cancellation alone do not
trigger it. ``always`` opens the full workflow report when there are no active
errors. ``on-errors`` and null leave successful runs closed. Process/test outcomes
are unchanged. One aggregate opening suppresses child openings.

Opening is disabled in CX and dry runs; workflow execution itself remains
local-only. Preflight failures have no report to open. A failed summary write
does not open an older file, and a missing browser does not affect the exit code.
Child report opening is deferred until the workflow finishes. When the workflow
policy selects its successfully written summary, child reports are not opened.
Otherwise child policies apply, using retained report snapshots. A summary-write
failure also falls back to those child policies. Browser unavailability does not
trigger a cascade of child tabs. The summary table links only child HTML reports;
JSON files remain available for automation. Workflow ``on-errors`` uses a hyphen; job ``on_errors``
retains its existing spelling.

``ptk maintainer sync tasks`` adds ``ptk: workflow NAME`` tasks alongside job tasks.
Generated workflow tasks use the owner repository's default variant and its
repository mappings. The Project Toolkit extension also offers an owner variant
selector. Regeneration preserves user tasks and is checked with ``--check``.

At VMR level, ``ptk maintainer sync tasks`` generates workspace tasks for workspace
and repository-qualified workflows. ``ptk ALIAS maintainer sync tasks`` generates
that member's job and workflow tasks. Workspace task synchronization updates
member tasks too; synchronize authoring resources separately with
``ptk maintainer sync agent``. The generated VMR tasks set their
working directory to the workspace root. Offline skills and examples are installed
with the normal authoring bundle; see :doc:`/guides/editor`.

Planned GitHub template generation (not implemented)
----------------------------------------------------

Native GitHub workflow generation remains a draft proposal. A future generator
could map invocation IDs and ``needs`` directly to GitHub jobs and dependencies.
Checkout, artifact handoff, permissions, variant mapping and exact failure
semantics would still need a separate design. No generation command or generic
PTK run-job GitHub Action is currently available.

Owner variant mappings
----------------------

A workflow's owning repository defines cross-repository selections in its variant
configuration. The following belongs inside the existing ``variants`` section::

   default: debug
   variants:
     debug:
       repo_variants:
         backend: development
         bootloader: debug
     release:
       repo_variants:
         backend: production
         bootloader: release

``ptk -V debug frontend workflow run verify`` selects ``frontend``'s ``debug``
variant. Its own job calls use that variant; calls to ``backend`` use
``development`` and calls to ``bootloader`` use ``debug``. Without ``-V``, the
owner's configured default is selected. Select one owner variant per workflow
invocation. Mappings inherit through ``extends``; a child's entries override its
parents' entries by repository alias.

A missing mapping for a referenced variant-enabled repository, an unknown target
variant or an invalid owner variant fails before jobs execute or outputs are
deleted. Repositories without variants need no mapping; mapping a variant to
such a repository is an error. Names are VMR repository aliases, not directory
paths. Workflow calls do not accept ``variant``; configure cross-repository selections
with ``repo_variants``. Dry runs print the resolved repository/job/variant for each
call; clean and re-run use those same selections.

Optional reuse of dependent jobs
--------------------------------

Configure ``outputs`` and ``cache: true`` on the project job definition to allow
whole-job reuse after successful unchanged prerequisites. All workflow roots
always run. A dependent checks every prerequisite's explicit job outputs and its
own existing outputs; job outputs are not inferred from step outputs. A missed
job-level check still permits eligible step-level reuse.

``ptk workflow run NAME --no-cache-ptk`` (or ``ptk NAME --no-cache-ptk``) disables
PTK reuse for every child job and step, including calls into other repositories.
Outputs primarily describe artifacts for workflow uploads and downloads; the
project owns their validity, cache policy and transfer operations. See
:doc:`output-reuse` for examples and the full contract.
