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
   :tags: implemented

   PTK shall accept multiple eligible job variants, prepare each variant separately and execute selected variants concurrently with distinct outputs.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

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
   :verification_criteria: Filesystem snapshots remain unchanged and fake/real process observers see no job step execution during dry-run.
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
   :verification_criteria: Control tests cover successful retries, exhausted retries, skipped conditions, timeout and group failure outcomes.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall honor configured conditions, sequential/parallel groups, retries, timeouts and continue-on-error rules and preserve failure information in results.

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

.. req-sw:: Join finite background work
   :id: REQ_Sw_BACKGROUND
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Background tests cover joining, failure, timeout and cancellation without orphaned unbounded job work.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall associate background steps with an execution scope and join them at its defined boundary before completing that scope.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/run.py``; ``tests/test_background.py``.

.. req-sw:: Schedule local job workflows
   :id: REQ_Sw_WORKFLOWS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Workflow CLI and scheduler tests cover member ownership, nesting, concurrency limits and CI rejection.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall resolve workflow calls to jobs and variants in their owning repositories, enforce one concurrency limit across nested parallel groups, and reject local workflow execution in CI.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

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
