Execution and variants
======================

Preparation, scheduling, isolation, cancellation and output lifecycle.

.. req-sw:: Run several job variants in parallel
   :id: REQ_Sw_MULTI_VARIANT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Multi-variant CLI tests produce one result per selected variant and reject disallowed selections before running.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: partial

   PTK shall accept multiple eligible job variants, prepare each variant separately and execute selected variants concurrently with distinct outputs.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Partial: the CLI prepares the full selection but executes variants in order. The extension launches separate variant tasks concurrently; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/jobs.py``; ``tests/test_cli_jobs.py``.

.. req-sw:: Validate concrete variant selections
   :id: REQ_Sw_VARIANT_CONSTRAINTS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Valid selections resolve; cycles, invalid features and unsatisfied selected-component dependencies fail validation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall resolve variant inheritance, typed features, selected components and constraints, applying component-local constraints only when that component is selected.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/variants/rules.py``; ``tests/unit/test_variants.py``.

.. req-sw:: Resolve parameters before execution
   :id: REQ_Sw_PARAMETER_PREPARATION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Missing required values and invalid templated defaults fail preparation before a command executes.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall resolve and validate required parameter values for each selected concrete variant before starting its job steps.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/run.py``; ``tests/test_run.py``.

.. req-sw:: Compose an isolated job environment
   :id: REQ_Sw_ENVIRONMENT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Caller virtualenv selectors and unrelated variables do not leak into an ordinary isolated job; explicit inheritance is honored.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall compose command environments from a filtered base plus declared variables, permitted caller values, selected tools and runtime paths.

   **Scope:** Environment composition does not provide filesystem, process,
   network or device sandboxing. Commands and Python tools retain the user's
   permissions; per-step directories do not enforce an access boundary.
   Projects choose and implement any required isolation. This responsibility
   remains with the project implementation to preserve flexibility in its tools
   and execution policies.
   See :need:`DD_EXECUTION_BOUNDARIES`.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/execution/environment.py``; ``tests/test_run.py``.

.. req-sw:: Select job Python environments independently
   :id: REQ_Sw_PYTHON_RUNTIME
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Python runtime tests show the configured interpreter and environment are used without redirecting synchronization into PTK installation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall resolve declared Python job runtimes independently of the environment running PTK and apply their selected project/group requirements.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/python_env.py``; ``tests/test_run.py``.

.. req-sw:: Preview without executing jobs
   :id: REQ_Sw_DRY_RUN
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Only graph previews are written; run-output snapshots remain unchanged and process observers see no job step execution during dry-run.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall support job/workflow dry runs that resolve a plan without executing steps, installing tools or writing run reports.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/run.py``; ``tests/test_quickstart.py``.

.. req-sw:: Apply step execution controls
   :id: REQ_Sw_CONTROL
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Control tests cover successful retries, exhausted retries, skipped conditions, timeout and dependency failure outcomes.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall honor configured conditions, explicit step dependencies, bounded concurrency, retries, timeouts and continue-on-error rules and preserve failure information in results.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/execution/planning.py``; ``tests/test_controls.py``.

.. req-sw:: Cancel active and pending work
   :id: REQ_Sw_CANCEL
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Native process tests and scheduler tests observe terminated active work and no later queued execution.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall propagate cancellation to active process trees and cooperative handlers and prevent queued workflow calls from starting after cancellation.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/process.py``; ``tests/workflows/test_scheduler.py``.

.. req-sw:: Complete all scheduled step work
   :id: REQ_Sw_BACKGROUND
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Step graph tests verify overlapping independent commands, joins, failure propagation, timeout and cancellation without orphaned work.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall wait for all active steps before completing a job, scheduling ready steps by explicit dependencies within the configured worker limit.

   **Origin:** The approved step dependency design supersedes the previous background-mode mechanism while retaining the requirement to join active work.

   **Implementation:** Implemented; the tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``tests/test_step_graphs.py``; ``tests/test_controls.py``.

.. req-sw:: Select a dependency closure or one explicit step
   :id: REQ_Sw_STEP_SELECTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Tests verify out-of-order declarations, transitive prerequisite selection, exclusion of unrelated work, mutually exclusive options and omitted-prerequisite notices in preview and report.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall support selecting a target step with all its transitive prerequisites, or explicitly selecting only that step while listing omitted prerequisites and requiring the user to supply necessary existing outputs.

   **Origin:** User-approved partial execution option 3.

   **Implementation:** Implemented; the tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``tests/test_step_graphs.py``; ``tests/unit/test_execution.py``.

.. req-sw:: Inspect execution dependency graphs
   :id: REQ_Sw_GRAPH_INSPECTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Graph tests verify execution-direction trees, bounded shared references, disconnected targets and partial selections; offline browser checks verify all nodes/edges, layout and controls. Both dry-run paths include previews without executing commands.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall expose job and workflow dependency graphs through a graph-only option and include them automatically in dry-run output. Terminal trees shall start with nodes without prerequisites, nest dependents under their prerequisites, retain authored root/sibling order and expand shared nodes once. Joins shall list every prerequisite and remain subject to all declared needs. Offline HTML diagrams shall retain one node per invocation and all dependency edges directed from prerequisites to dependents, with zoom, fit, pan and node details. Selection, variant and known skip information shall remain visible.

   **Scope:** Graphs represent declared scheduling dependencies. They do not
   discover file inputs/outputs or guarantee artifact existence, freshness,
   correctness, sandboxing or freedom from shared-resource races. Project
   implementations own these semantics and report their outcomes. This is an
   intentional boundary that preserves project flexibility, rather than an
   obligation for PTK to monitor or validate arbitrary script operations. See
   :need:`DD_EXECUTION_BOUNDARIES`.

   **Origin:** User request for graph inspection and automatic dry-run graphs.

   **Implementation:** Implemented; the tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``tests/test_step_graphs.py``; ``tests/test_graph_presentation.py``; ``tests/workflows/test_cli.py``; ``extensions/project-toolkit/test/graph-ui.test.js``.

.. req-sw:: Schedule local job workflows
   :id: REQ_Sw_WORKFLOWS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Workflow CLI and scheduler tests cover qualified member targets, graph validation, dependency readiness, branch failures, resource conflicts, concurrency limits and CX rejection.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall define workflows as named job invocations with explicit needs dependencies, resolve qualified REPO:JOB targets and owner variant mappings, reject invalid graphs before execution, schedule ready jobs within one concurrency limit, block dependents of failed or skipped prerequisites unless failure is tolerated, and reject local workflow execution in CX mode.

   Each repository/job pair shall occur at most once per workflow, including
   sequential calls and local/owner-qualified spellings of the same target.
   Identical job names in different repositories remain distinct. Configuration
   validation shall detect cycles and duplicate targets before execution.

   **Origin:** User-approved workflow jobs/needs design, including qualified VMR targets and removal of group-based workflow scheduling.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/workflow.py``; ``tests/workflows/test_scheduler.py``.

.. req-sw:: Reject overlapping run storage
   :id: REQ_Sw_RUN_LOCK
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: A second writer for the same job/variant fails with a lock diagnostic while independent jobs retain separate outputs.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall reject concurrent runs targeting the same job/variant storage while allowing independent jobs or variants to proceed.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/locking.py``; ``tests/test_cleanup.py``.

.. req-sw:: Bound cleanup to owned outputs
   :id: REQ_Sw_CLEAN
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Cleanup tests verify all targets before deletion, dry-run preservation, and explicit confirmation for clean-all operations.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall preflight requested output cleanup and reject repository roots, escaping/symlink paths, configuration/Git metadata, tracked sources and active run locks.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/cleanup.py``; ``tests/test_cleanup.py``.

.. req-sw:: Generate variant inputs within the consuming step lifecycle
   :id: REQ_Sw_STEP_GENERATORS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Command, Python, built-in operation and generation-only steps receive files before execution; overrides and retries retain the prepared snapshot; dry-run, skipped and blocked steps generate nothing; failures prevent the command; concurrent variants/steps use distinct folders.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall accept an ordered, unique generators list on any job step and run it
   before each execution attempt from the prepared resolved variant. It shall
   write outputs only inside that step's build directory without changing cwd.
   It shall reject unknown enabled generators and missing variant selections
   during preparation, validate all generated names/content before writing, and
   stop before the command if generation fails or cancellation is observed.

   **Origin:** Explicit user request for per-step generators before commands and
   Python scripts, with generated files in the step folder.

   **Implementation:** Implemented. Per-file replacement is atomic; multi-file
   transactions, script sandboxing, artifact correctness and repeat-run isolation
   are not promised. In-process generator cancellation is cooperative. CLI concurrent
   variant scheduling remains separate under :need:`REQ_Sw_MULTI_VARIANT`.

   **Evidence:** ``src/ptk/application/use_cases/run.py``;
   ``src/ptk/adapters/variant_files.py``; ``tests/test_step_generators.py``.
