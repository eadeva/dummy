Execution and variants
======================

Preparation, scheduling, isolation, cancellation and output lifecycle.

.. req-sw:: Reuse explicitly declared outputs as an optional project-owned aid
   :id: REQ_Sw_OUTPUT_REUSE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Real command, built-in, workflow and CLI tests verify opt-in declarations, always-run roots, unchanged dependency reuse, content/configuration invalidation, failure handling, execution-wide bypass, report provenance and extension guidance.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall accept project-owned file/folder outputs on jobs and steps,
   principally as artifact declarations for workflow uploads and downloads.
   Declarations shall not imply file transfer. Built-in caching shall be an
   optional aid requiring explicit outputs and cache: true, with correctness
   owned by the project and no inferred run.build_dir fallback.

   Root steps and root workflow jobs shall always execute. Successful dependents
   may reuse existing outputs only when every declared prerequisite output,
   resolved execution configuration and own output fingerprint matches a prior
   successful receipt. Whole-job reuse shall apply only to dependent workflow
   calls. No artifact copies or restoration shall be introduced.

   --no-cache-ptk shall bypass reuse for all jobs and steps in the invocation,
   without changing native tool caches. Reports shall distinguish reused work
   and its source run, preserving zero execution attempts and avoiding claims of
   newly executed tests. Extension configuration shall explain output purpose,
   optional caching and project responsibility.

   **Origin:** User request for lightweight built-in caching, explicit outputs,
   workflow extrapolation, global bypass and project ownership documentation.

   **Implementation:** See :need:`DD_OUTPUT_REUSE` and :doc:`/guides/output-reuse`.
   Tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``tests/test_output_cache.py``;
   ``extensions/project-toolkit/test/schema.test.js``;
   ``extensions/project-toolkit/test/integration.test.js``.

.. req-sw:: Launch GUI jobs independently of PTK
   :id: REQ_Sw_GUI_JOBS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Real CLI tests exit while a launched Python/program process remains alive; failed preparation and process creation remain failures, dry runs launch nothing, and extension tests place GUI jobs in a distinct themed branch.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall accept a boolean job-level ``gui`` setting, execute prerequisite
   steps normally and detach the unique final command. The extension shall
   expose these jobs under GUIs with a distinct icon and color, preserving
   normal job permissions, variants, parameters and actions. It shall give
   scalar configuration fields a standard field icon and use semantic,
   theme-aware colors consistently across tree and form.

   **Origin:** User request for GUI launch jobs and configuration tree color/icon review.

   **Implementation:** Launch receipts record process creation, not application
   completion. No lifetime timeout/retry, terminal pipes or exit monitoring are
   attached to the GUI. Desktop connection variables survive isolation while
   explicit overrides remain authoritative. See :need:`DD_GUI_JOBS`.

   **Evidence:** ``tests/test_gui_jobs.py``; ``extensions/project-toolkit/test/extension.test.js``; ``extensions/project-toolkit/test/presentation.test.js``.

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
   :verification_criteria: Runtime/schema tests verify standalone script execution, requirements-environment creation/reuse and invalidation, project/group command construction, mutually exclusive settings, and the repository's separate job environments; a packaged-tool integration test verifies actual uv execution and exit status. Review the guide against runtime command construction and uv's editable-project contract.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall support standalone Python scripts through uv and explicit selection
   of exactly one Python runtime: a uv project with optional dependency groups,
   a requirements/packages environment with an optional Python request, a uvx
   package with optional extra packages, or PTK's own interpreter. Ordinary
   interpreter commands shall remain executable without Python-mode configuration.
   The selected runtime shall apply to command steps without activating or
   replacing PTK's parent process environment.

   The user guide shall describe script, module and inline-code forms, editable
   local project execution, working-directory rules and environment/cache
   ownership. It shall distinguish dependency installation from output reuse.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Constraints:** uv controls project synchronization and editable installation;
   the project must provide suitable package/build metadata. PTK does not add a
   frozen-lockfile policy, an editable toggle or implicit source-file invalidation
   for output caching. Requirements-environment reuse is not a transitive lock.
   See :need:`DD_PYTHON_RUNTIME` and :doc:`/guides/python-tools`.

   **Evidence:** ``src/ptk/adapters/python_env.py``;
   ``src/ptk/domain/execution/commands.py``; ``tests/test_run.py``;
   ``tests/test_repository_config.py``; ``tests/test_python_tool_package.py``.

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

.. req-sw:: Export a minimal CX setup matrix
   :id: REQ_Sw_CX_MATRIX
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: CLI tests verify eligible concrete variant/job pairs, aliases, executable argv, version/source commit, common/per-job destination bases, GitHub output lines, empty matrices, runtime-dependent output declarations left untouched, VMR ownership and CX access without maintenance elevation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall provide a hidden built-in maintainer matrix command usable locally
   by maintainers and in CX without requiring a human maintainer identity.
   It shall expose only variant/repository/job identifiers, invocation arguments,
   version/source commit and configured upload destinations, including the shared
   base before job suffixes. It shall honor job eligibility and role restrictions.
   GitHub needs identifies producer jobs for downloads. Actual output paths and
   step/artifact_type properties belong to the completed producer job; setup
   shall neither predict those paths nor introduce a separate input mapping.

   **Origin:** User request for a variant-matrix command in the first GitHub
   workflow job, with minimal execution/upload/download information and a common
   upload base; optional assistance for initial workflow setup.

   **Implementation:** Implemented. The export does not execute jobs, install
   tools, transfer artifacts or generate pipeline files. Configured version
   discovery may run when resolving artifact routes. Project workflows retain
   responsibility for parameters, runner selection, dependencies and transfers.

   **Evidence:** ``src/ptk/application/use_cases/matrix.py``;
   ``src/ptk/drivers/cli/matrix.py``; ``tests/test_matrix_export.py``.

.. req-sw:: Summarize declared outputs and generate upload configuration
   :id: REQ_Sw_UPLOAD_CONFIGURATION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Execution tests verify runtime paths, typed and untyped declarations, output availability, producer properties, missing/failed/partial outputs, cache provenance, secret masking, dry-run preservation, atomic-write failures, report serialization and history/workflow snapshots.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall show declared output paths and availability in completed job
   summaries and reports and generate a versioned upload configuration containing
   available files/directories and producer properties. It shall accept optional
   artifact_type metadata without inferring output paths or changing cache opt-in.
   It shall leave transfer credentials, destination selection and actual uploads
   to workflow commands. Native GitHub needs remains the producer-job selector.

   **Origin:** User request for output paths in execution summaries and an upload
   configuration generated after execution, with producer step and artifact type
   distinguishing multiple outputs.

   **Implementation:** Implemented. Availability is not a guarantee of artifact
   correctness or freshness. Manifest history preserves metadata rather than file
   contents; a manifest write failure does not change the process result.

   **Evidence:** ``src/ptk/adapters/uploads.py``;
   ``src/ptk/domain/run_output.py``; ``tests/test_upload_configuration.py``.

.. req-sw:: Transfer declared GitHub job outputs through Artifactory
   :id: REQ_Sw_GITHUB_ARTIFACTS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Tests verify file/ZIP round trips, relative path and permission restoration, VMR producer paths, checksum and identity checks, traversal/symlink/overlap rejection, protected properties, credential handling and exact run-result handoff.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall ship ptk-upload, ptk-download and ptk-run-job composite Actions.
   Upload shall use curl with technical-user/token credentials, ZIP directories,
   upload files directly and retain declared producer properties plus additional
   properties. Download shall select producers declared in GitHub needs, verify
   identity and checksums, restore files and unzip directories at their original
   repository-relative paths. The run Action shall expose those paths and the
   completed execution's upload manifest without searching for stale logs.

   **Origin:** User request for upload/download/job Actions using declared outputs,
   technical-user credentials, ZIP folders and repository-relative restoration.

   **Implementation:** Implemented with local round-trip and integration tests;
   live Artifactory and hosted GitHub execution remain unverified.

   **Decision:** Setup selectors and a run-scoped remote manifest avoid ambiguous
   property searches and matrix job output races. PTK is preinstalled in the
   project's Docker image. See :need:`DD_GITHUB_ACTIONS`.

   **Evidence:** ``src/ptk/adapters/github_actions.py``;
   ``.github/actions``; ``tests/test_github_actions.py``.
