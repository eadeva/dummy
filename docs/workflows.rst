Local action workflows
======================

Workflows orchestrate existing PTK actions **on the developer's machine**. They
require neither GitHub nor a CI runner. Run one from the terminal or a generated
VS Code task. Each action keeps its repository, variant, tool requirements,
credentials, environment, maintainers and ordinary logs/reports.

``ptk workflow run`` refuses CX/CI mode, whether detected or forced with ``--ci``.
``list``, ``show`` and ``dry-run`` are inspection operations and remain available.
GitHub template generation and a generic PTK action for those generated workflows
are a separate future phase; neither is implemented by this feature.

Files and commands
------------------

Put ``workflow.ptk.yml`` directly in ``repository.config_path``. PTK loads it
once as a conventional defaults layer before explicit main/includes, then CX and
local overlays. An explicitly included copy retains its include position. More
workflow files can be included with the normal YAML loader. Keep ``.main.ptk.yml``
minimal. Names use lowercase letters, digits and hyphens, starting with a letter.
Workflows and actions have separate namespaces::

   ptk workflow list
   ptk workflow show verify
   ptk workflow dry-run verify
   ptk workflow run verify
   ptk verify

Workflow shortcuts appear alongside actions in ``ptk --help``. If an action and
workflow share a name, the local terminal prompts for ``action`` or ``workflow``.
CX selects the action without prompting. Non-interactive local callers must use
``ptk run verify`` or ``ptk workflow run verify`` explicitly. Help never prompts.
Built-in commands and VMR repository aliases retain priority over shortcuts;
such workflows remain accessible through ``workflow run``.

A complete repository-owned workflow:

.. literalinclude:: ../examples/workflows/app/config/workflow.ptk.yml
   :language: yaml

The example lives in a small manual VMR. From ``examples/workflows`` run::

   ptk workflow list
   ptk workflow run all
   ptk workflow run frontend/verify
   ptk frontend workflow run verify
   ptk frontend/verify
   ptk frontend verify

Copy the example to a temporary folder before trying it if you want to preserve
the documentation tree. Its actions use portable built-ins, without compilers,
network access or credentials.

Action calls and groups
-----------------------

``steps`` is an ordered list of named entries. A leaf has:

* ``action``: an existing action name; ``- build: build`` is shorthand.
* ``repo``: a VMR repository alias. Omission means the workflow's owner.
* ``variant``: one concrete variant name or its alias. Omission uses that
  repository's normal selected/default variant. There is no cross-repository
  global variant selection or implicit variant matrix.
* ``params``: values for parameters already declared by the target action.
  Values use that action's types, choices and validation. Secret parameters are
  not configurable in a workflow; keep secrets in the target action's credential
  declarations rather than workflow YAML or parameters.
* ``continue_on_error``: default false; tolerate this call's failure for workflow
  sequencing and exit status. The child report still records the failure.

A group replaces ``action`` with nested ``steps`` and optionally ``parallel: true``.
It can also set ``continue_on_error``. Groups cannot set ``repo``, ``variant`` or
``params``; make each call's repository context explicit. Sibling entry names must
be unique. Workflow entries call actions, never other workflows or arbitrary shell
commands. Put shell commands, retries, step timeouts, skip filters and cleanup
inside the target action, using the existing action/step model.

The workflow itself accepts ``help``, ``audience: all|maintainer``, ``open_report``, ``steps``,
``parallel`` (false by default), and ``max_workers`` (default 4, range 1–32).
The worker limit applies to active **action calls** across nested groups, not to
parallel steps inside those actions. No new global environment is merged across
repositories. Ordinary action parameter defaults, version discovery and
``requires_tools`` overrides continue to apply.

Failure, preflight and isolation
--------------------------------

PTK prepares every action before starting the first. Unknown repositories/actions,
invalid parameters/variants, missing prerequisites and maintainer restrictions
fail the preflight. Credentials are resolved serially before parallel execution,
so there are no concurrent credential prompts. Each call gets its own application
and prepared run. Versions are discovered during this preflight and retained for
that call; a previous action changing Git state does not refresh later snapshots.

A dry run resolves configuration and plans the calls, but creates no run outputs,
installs no tools and does not resolve credentials. As with action previews,
custom version-discovery commands can execute and must be read-only. Workflow
previews list action calls and grouping; use the target action's ``dry-run`` to
inspect its individual commands.

Sequential execution stops after an untolerated failure; remaining entries are
recorded as skipped. Parallel branches finish independently even if a sibling
fails. Subsequent sequential entries wait for the whole parallel group.
``continue_on_error`` tolerates failure, not cancellation. Ctrl+C propagates
cancellation to active action runners and prevents queued calls from starting.
The workflow returns exit code 0 for success/tolerated failures, 1 for action
failure and 130 for cancellation. Preflight/configuration errors use exit code 2.

Parallel branches may not share the same repository/action/variant output folders.
They also may not share a ``python.project`` environment, since uv can synchronize
that project's shared virtual environment while another action is using it.
For parallel actions in one project, set a distinct absolute
``env.UV_PROJECT_ENVIRONMENT`` on each action, for example
``${project.root}/.ptk/venvs/package``. PTK checks the resolved environment paths,
including step-level overrides. Use absolute paths for uv workspace members so
the environment location does not depend on uv's workspace-root discovery.
PTK's own ``verify`` workflow runs ``check``, ``test`` and ``package`` sequentially,
alongside ``docs``; these actions have separate environments. Existing action locks
also protect against a separate PTK invocation using the same output folders.
PTK cannot infer arbitrary paths or external resources used by scripts: authors
must sequence actions that write the same files, hardware device or service.

Tool selection remains per action. Toolbase-only definitions are ignored outside
Windows; Docker installation policy still applies. Workflow preflight expects
prerequisites already available unless an action handles its own checks through
``tools.ensure``. There is no workflow-wide installer. Install under the target
repository/action before the run.

VMR ownership
-------------

At the VMR root, an optional ``workflow.ptk.yml`` holds workspace-owned workflows.
It needs only a ``workflows`` mapping, not a project entry file, and supports normal
includes. Every workspace-owned leaf must specify ``repo``. Only discovered,
configured VMR members can be referenced; filesystem paths are not repo selectors.

.. literalinclude:: ../examples/workflows/workflow.ptk.yml
   :language: yaml

Workspace-owned names are unqualified, for example ``all``. Member-owned names
are qualified, for example ``frontend/verify``; identical names in different
repositories never merge. Under ``ptk frontend workflow``, use the local name
``verify``. Manual VMR members should be invoked from the workspace root to retain
membership context. An explicit ``-c`` entry selects that repository's command
surface; automatic Git-pointer membership can still resolve its dependencies.

An owner workflow's ``audience`` and ``command_audience.workflow`` policy are
checked along with the target action's actual repository role. A public workflow
cannot bypass a maintainer-only action. Workspace-owned maintainer workflows
require ``PTK_ROLE=maintainer`` because a workspace marker has no maintainer file;
member action roles still use their own repository settings. These role policies
remain a developer convenience, not an operating-system security boundary.

Reports and editor tasks
------------------------

Each action writes its normal reports and applies its ``open_report`` policy.
The workflow also writes an immutable summary and child HTML/JSON reports under::

   _reports/workflows/NAME/RUN-ID/workflow.json
   _reports/workflows/NAME/RUN-ID/workflow.html
   _reports/workflows/NAME/RUN-ID/actions/STEP-PATH/report.html

Repository-owned workflows honor the owner's layout/report directory; workspace
workflows use the workspace's ``_reports``. Child report snapshots include their
own log copies so repeated sequential calls do not redirect earlier report links
to newer logs. Workflow reports use colored status cards and per-column filters.
Open a child report for its project versions, tool dependencies and test details.
Workflow history is retained until explicitly removed; it has no automatic rotation.

The workflow opens its summary HTML report automatically after a local run.
Set the policy on the workflow, independently of each action's report policy::

   workflows:
     verify:
       open_report: always  # default; on-errors opens only when errors are present
       steps:
         - check: {action: check}
         - test: {action: test}

``on-errors`` includes failed action calls, tolerated failures in nested groups,
failed steps or tests, error findings and child report/import problems. It does
not change the workflow exit status. Warnings, skips and cancellation alone do
not count as errors. ``always`` also opens a successfully written cancellation
report. Set ``open_report: null`` to disable workflow report opening.

Opening is disabled in CX/CI and dry runs; workflow execution itself remains
local-only. Preflight failures have no report to open. A failed summary write
does not open an older file, and a missing browser does not affect the exit code.
Child report opening is deferred until the workflow finishes. When the workflow
policy selects its successfully written summary, child reports are not opened.
Otherwise child policies apply, using retained report snapshots. A summary-write
failure also falls back to those child policies. Browser unavailability does not
trigger a cascade of child tabs. The summary table links only child HTML reports;
JSON files remain available for automation. Workflow ``on-errors`` uses a hyphen; action ``on_errors``
retains its existing spelling.

``ptk setup vscode tasks`` adds ``ptk: workflow NAME`` tasks alongside action tasks.
Workflow tasks use their configured per-call variants and have no global variant
picker. Regeneration preserves user tasks and is checked with ``--check``.

At VMR level, ``ptk setup vscode tasks`` generates workspace tasks for workspace
and repository-qualified workflows. ``ptk ALIAS setup vscode tasks`` generates
that member's action and workflow tasks. ``ptk setup vscode`` installs member
skills/tasks and the workspace workflow tasks. The generated VMR tasks set their
working directory to the workspace root. Offline skills and examples are installed
with the normal authoring bundle; see :doc:`editor`.

Planned GitHub template generation (not implemented)
----------------------------------------------------

The next phase will add ``ptk setup init --workflows``. Each action call becomes
one GitHub job using a generic PTK run-action GitHub Action; a local workflow
is not executed wholesale on a CX runner. The job records that call's repository,
action, variant and parameters.

Dependency translation is structural:

* An action job needs the terminal jobs of the preceding sequential group.
* Parallel siblings receive the same incoming dependencies and have no dependency
  edges between one another.
* A step after a parallel group needs all terminal jobs of that group.
* Apply these rules recursively to nested groups; groups themselves are not jobs.

For ``build -> [tests, lint] -> package``, tests and lint each need build, and
package needs both tests and lint. Preserve failure/continuation semantics when
adding generation, including group-level continuation; do not blindly flatten
those policies into a different execution order. Job identifiers must be stable
and unique even when the same action is called more than once. Checkout, artifact
handoff, GitHub permissions and the reusable action are also future work.
