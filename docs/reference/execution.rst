Step dependency execution
=========================

Jobs contain a mapping of named steps. Each step has one ``run`` command or
``uses`` handler. ``needs`` names prerequisite step IDs in the same job::

   # config/ptk/jobs/build.ptk.yml
   max_workers: 4
   steps:
     configure:
       run: [cmake, -S, ., -B, "${run.build_dir}"]
     compile:
       needs: configure
       run: [cmake, --build, "${steps.configure.build_dir}"]
     lint:
       run: [python, tools/lint.py]
     package:
       needs: [compile, lint]
       run: [python, tools/package.py]

``configure`` and ``lint`` are immediately eligible. ``compile`` starts as soon
as ``configure`` succeeds, even while ``lint`` is running. ``package`` waits for
both prerequisites. YAML declaration order affects display order, not dependencies.
``max_workers`` limits active steps in this job; a workflow has its own limit for
active jobs. These limits compose, so several workflow jobs can each run several
steps. Choose limits to suit the machine and external tools' own worker counts.

Loading rejects missing, repeated and self dependencies, invalid IDs and cycles.
IDs must also produce distinct output folder names across supported platforms
(including case-insensitive filesystems). IDs are unique mapping keys, begin with a letter or digit and contain only
letters, digits, underscores, dots or hyphens. Duplicate YAML keys are errors.
There are no nested step groups, background mode or implicit ordering.

Failure, conditions and cancellation
------------------------------------

A node starts after all its prerequisites pass. A failed, skipped or cancelled
prerequisite blocks its dependent chain, with a reason in the results. Independent
branches continue. ``continue_on_error: true`` tolerates a failed step and releases
its dependents; the failure remains visible in logs and reports. It does not turn
a skipped or cancelled prerequisite into a success.

``when``, variant restrictions and ``only_cx`` can skip a step. Dependents are
then skipped too. For optional checks which must not block another branch,
author the dependencies accordingly. ``retries`` and ``timeout`` apply to one
step; retrying a step does not rerun its prerequisites. Python handlers must
cooperate with cancellation/deadline tokens. Ctrl+C signals active process trees,
cancels pending work and waits for running work to finish shutting down.

Working directories, outputs and responsibility
-----------------------------------------------

The default ``cwd`` remains the repository root. Set ``cwd`` explicitly when a
command needs another directory. Each step receives separate build, report and
log paths. These are storage conventions, **not a filesystem sandbox**: project
scripts and commands can write outside those paths.

Inside a step, ``${run.build_dir}``, ``${run.reports_dir}`` and
``${run.log_file}`` refer to that step's directories/file. To consume another
step's files, use ``${steps.ID.build_dir}``, ``${steps.ID.reports_dir}`` or
``${steps.ID.log_file}`` and declare the corresponding dependency. Dots in IDs
are supported. These references describe paths in the current run layout;
they do not prove that a prerequisite ran or that a file exists. PTK does not
publish arbitrary ``steps.ID.outputs.NAME`` values or restore previous-run outputs.

Job binaries are shared within the job/variant. Project authors must declare
ordering or isolate paths for shared files, caches, generated sources, hardware,
services and external systems. PTK rejects unordered ``python.project`` steps
that resolve to the same uv project environment, even with one worker. Separate
``UV_PROJECT_ENVIRONMENT`` values or a ``needs`` edge resolve that conflict.
PTK cannot infer every resource accessed by arbitrary commands.

.. _execution-boundaries:

Project responsibility and execution boundaries
------------------------------------------------

**Project implementation responsibility is intentional: it preserves flexibility
for projects.** Projects choose their languages, build tools, artifact layouts,
checks, caching, resource coordination and recovery policies. They can reuse
existing scripts and integrate hardware or external services without adapting
their internals to one PTK-specific build model.

PTK provides common orchestration and records the outcomes reported by those
implementations. Project scripts, Python packages and selected tools own the correctness
of their operations. PTK does not inspect or control their arbitrary internal
file and resource operations. Projects decide which validation and isolation
guarantees their work requires, implement them, and report failure when their
contracts are not met. This is the intended division of responsibility.

The dependency
graph represents **declared scheduling relationships**, not a discovered or
verified graph of file inputs and outputs. These boundaries apply equally to steps
inside a job and job invocations inside a workflow.

.. list-table:: Responsibility boundaries
   :header-rows: 1
   :widths: 20 35 45

   * - Area
     - PTK provides
     - Project implementation owns
   * - Dependencies
     - Validation of declared IDs and edges; scheduling after prerequisites pass
       or their failures are explicitly allowed.
     - All required ordering. PTK does not discover file reads/writes, infer
       missing edges, or transfer artifacts along an edge.
   * - Inputs and outputs
     - Configured storage paths, logging, report collection and managed cleanup.
     - Checks that required inputs exist and are current, and that commands
       produce the expected files, contents and versions. There is no general
       step input/output contract or automatic artifact validation.
   * - Isolation
     - Per-step storage conventions and composed command environments.
     - Any required filesystem, process, network or device isolation. Commands
       and Python tools execute with the user's permissions; PTK does not sandbox
       them or restrict them to their step directories.
   * - Concurrent resources
     - Worker limits, job/variant run locks, and preflight checks for known
       overlapping job storage and uv project environments.
     - Coordination of other shared files, caches, generated sources, devices
       and services. These checks are not a general resource-locking system and
       do not prevent unrelated processes from accessing those resources.
   * - Reuse and recovery
     - Explicit partial-run selection, retries, cancellation and retained run
       evidence.
     - Input freshness, safe reuse, repeatable side effects and recovery from
       partial writes. PTK does not perform dependency-based up-to-date checks,
       content-addressed artifact caching, automatic output restoration or
       transactional rollback of command side effects.

For example, if ``compile`` returns success without creating the expected binary,
``package`` can still become eligible through ``needs: compile``. The command or
handler must check that binary itself or declare a validation step which fails
when it is missing or invalid. A path such as ``${steps.compile.build_dir}``
identifies a location; it does not create a dependency or assert that anything
has been written there. An allowed failure can likewise release a consumer
without producing its required artifacts.

Distinct step folders and ``environment.isolate: true`` do not prevent a command
from writing into another step's directory or the repository. Setting ``cwd``
only changes the starting directory. Cleanup path checks protect PTK's own
cleanup operation; they do not restrict what an executed command can delete.
Use an explicitly configured external container, VM or other execution boundary
when isolation is required. Build tools invoked by PTK can enforce their own
input/output, caching or sandboxing rules; PTK does not add those guarantees.

Worker counts limit scheduled work, not total system load or exclusive resource
ownership. Workflow and job limits compose, invoked tools can start their own
workers, and other PTK runs or external processes may run concurrently.
``max_workers: 1`` is not a substitute for correct ``needs`` relationships.
Retries may repeat writes or remote actions; cancellation cannot undo completed
side effects. Project commands must handle those cases explicitly.

A graph preview therefore cannot prove that a build will work or that independent
branches are safe to run together. A green report node records the outcome
reported by the project implementation. The project is responsible for making
that outcome reflect its required artifact checks; PTK performs no independent
general validation of artifact correctness or reproducibility. See the
project-flexibility decision :need:`DD_EXECUTION_BOUNDARIES` and
:need:`DD_ROOT_CWD`.

Selecting part of a job
-----------------------

.. list-table:: Partial execution
   :header-rows: 1
   :widths: 30 70

   * - Invocation
     - Selected work
   * - ``ptk build``
     - All configured steps, subject to conditions and restrictions.
   * - ``ptk build --to package``
     - ``package`` and every transitive prerequisite; unrelated branches are omitted.
   * - ``ptk build --only-step compile``
     - Exactly ``compile``, bypassing prerequisite execution. The user is responsible for any required existing files or external state.

``--to`` and ``--only-step`` are mutually exclusive and accept completion for
step IDs. There is no ``--from`` option. ``--only-step`` does not bypass the
selected step's conditions, parameter validation, credentials or tool checks.
Its preview and report list the omitted prerequisites. A fresh or cleaned checkout
may lack required files; PTK never silently reads a historical run to repair this.
Current report inputs are reset for each run, so do not use retained reports as
an implicit build cache. Keep reusable build artifacts in explicit build locations.

Inspecting a graph
------------------

Both job and workflow dry-runs show their graphs automatically::

   ptk build --dry-run
   ptk workflow run verify --dry-run

Inspect only the configured graph, without preparing commands, resolving parameter
values or checking credentials/tools::

   ptk build --graph
   ptk workflow run verify --graph

Direct workflow commands and maintainer-prefixed routes support the same flag.
The terminal shows a compact tree in execution direction: **prerequisites →
dependents**. Steps without prerequisites are roots; each child directly depends
on its parent. For example, ``check`` is followed by ``test`` and then ``package``;
an independent ``docs`` step is a separate root. Roots and siblings retain their
authored order. Shared nodes expand once; subsequent occurrences say **shared —
shown above**.

A join lists **needs all** with every prerequisite. Its first occurrence under
one branch does not release it early: it still waits for every declared need.
The tree is a navigation projection, not a serial timeline; independent branches
can overlap. Redundant job labels are omitted when they match the invocation ID.

The preview links to a self-contained HTML diagram in ``.ptk/graphs``.
Prerequisites appear above their dependents and arrows point toward the work they
release, matching the tree's execution direction. The diagram has one box per
invocation, including all join edges.
Use **Zoom in**, **Zoom out**, **Fit to view**, or drag the canvas to pan. Select a
node (click, Enter or Space) to inspect its target, prerequisites and dependents;
select a dependency in the details panel to navigate to it. Long names wrap.
Layout uses bundled Dagre; no network service, Graphviz executable or Node
installation is needed to inspect a generated file. JavaScript must be enabled
for the interactive diagram.

Prepared job previews have separate files per concrete variant. Graph inspection
does not execute commands. A dry-run also shows the prepared selection and skip
reasons; omitted steps remain visible. ``--only-step`` lists prerequisites that
will not run and retains their edges. Generated graph previews are the only
preview files written; run outputs, logs and reports are untouched. ``--graph``
alone shows authored topology, not the outcome of runtime conditions.
The graph does not discover or verify artifact dependencies; see
:ref:`execution-boundaries`.

The extension consumes the same PTK-provided tree projection. Expand
prerequisites to inspect their dependents; both canonical nodes and shared
references edit the same configuration definition. There are no dependency-level
navigation groups. See :doc:`/guides/editor` and the decisions in
:doc:`/architecture/09-architecture-decisions`.

Graphs in execution reports
---------------------------

Every job and workflow HTML report contains a **Dependency graph** disclosure,
collapsed initially. Open it to use the same offline diagram controls. The
workflow graph shows job invocations with repository/job targets and the concrete
variant of each invocation. A child job report shows that job's steps.

Report graphs use the run's recorded dependencies and outcomes, not current YAML.
Later configuration changes therefore do not alter the graph on re-export.
Passed nodes are green, failed nodes red, skipped nodes grey, and cancelled or
allowed-failure nodes amber. Each node also spells out its state; failure allowed
remains explicit. Selecting a node shows its duration and recorded reason,
including blocked dependencies and steps omitted by partial execution. The
timeline remains the source of actual execution order and overlap.
Node colours describe recorded execution states, not checked input/output
contracts; see :ref:`execution-boundaries`.

``report: false`` excludes a step's details and results as before. Its ID and
prerequisite edges remain as a **Details hidden** node, so the graph cannot imply
that a dependency did not exist. Its message, command, duration, logs and result
are not exposed by the graph. The graph does not execute or rerun anything.

PTK output reuse
----------------

Jobs and steps support project-owned ``outputs`` and opt-in ``cache: true``.
Every root runs, and only dependents can reuse unchanged existing declared
outputs. ``--no-cache-ptk`` on a job or workflow disables all PTK reuse in that
invocation without changing tool-native caches. ``--re-run`` also bypasses reuse;
``--only-step`` never reuses the selected step. See :doc:`/guides/output-reuse`
for the complete matching, storage and reporting contract.
