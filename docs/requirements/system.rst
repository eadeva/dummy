System requirements
===================

This intentionally small system layer describes contracts across the CLI, shell,
filesystem, tools and integration boundaries. It does not introduce a hardware
level or repeat every software rule. Derived formulations remain under review.

.. req-sys:: Repository configuration contract
   :id: REQ_Sys_CONFIG
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Valid fixed-layout fixtures load; unsupported filenames, invalid values and escaped component paths fail before job execution.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_CONFIG
   :tags: implemented

   PTK shall discover one project marker, assemble only the conventional documents it owns, and reject invalid configuration with source diagnostics.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/project.py``; ``tests/test_fixed_config.py``.

.. req-sys:: Terminal command contract
   :id: REQ_Sys_CLI
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: CLI tests exercise command namespaces, parameter errors, missing-project validation and completion without executing jobs.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_CLI
   :tags: implemented

   PTK shall expose built-in diagnostic/setup groups and authorized configured jobs/workflows, with typed options, help, completion and process exit status.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/main.py``; ``tests/test_cli_namespaces.py``.

.. req-sys:: Shell profile integration
   :id: REQ_Sys_COMPLETION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Profile setup is repeatable; an independent shell resolves PTK on PATH and obtains command and value candidates.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_COMPLETION
   :tags: implemented

   PTK shall install shell-specific completion for the current user without requiring activation of the PTK Python environment.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/completion_profiles.py``; ``tests/test_completion_profiles.py``.

.. req-sys:: Job and workflow execution contract
   :id: REQ_Sys_EXECUTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Execution tests cover multiple variants, workflow dependency scheduling, failure propagation, timeout and cancellation.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_EXECUTION, REQ_Stkh_VARIANTS
   :tags: implemented

   PTK shall execute selected job/variant plans with declared inputs, controlled environments, bounded concurrency and cancellation, and return an outcome reflecting execution failure.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/run.py``; ``tests/test_run.py``.

.. req-sys:: Installation and package contract
   :id: REQ_Sys_DISTRIBUTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Build an sdist, rebuild its wheel, install that wheel in a separate project and verify resources and self-service setup entry points.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_DISTRIBUTION
   :tags: implemented

   PTK shall provide installable Python artifacts containing version-matched optional editor and authoring resources, with explicit per-user setup operations.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/extension_bundle.py``; ``tests/test_package_build.py``.

.. req-sys:: Installed version preservation
   :id: REQ_Sys_UPGRADE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Install version B, select older version A, and verify B remains executable; repeat for equal/newer selections and all supported package-source modes.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_KEEP_NEWER
   :tags: planned

   When a selected package is older than the installed PTK, the installer shall preserve the newer Python package and report the decision.

   **Origin:** Direct refinement of the accepted keep-newer request; not implemented.

   **Implementation:** Not implemented. No passing verification result is claimed.

   **Evidence:** ``install/install.ps1``.

.. req-sys:: Canonical result and history contract
   :id: REQ_Sys_REPORTS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: A later run does not replace the inputs of a retained run; supported exporters consume its canonical results.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_RESULTS
   :tags: implemented

   PTK shall capture execution evidence and normalize supported result formats for current and historical export without rerunning the job.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/report.py``; ``tests/test_reporting.py``.

.. req-sys:: Diagnostic interpretation contract
   :id: REQ_Sys_LOGS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Ignore/justify policies affect findings and report filters but do not turn a failed command or test into success.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_LOG_ANALYSIS
   :tags: implemented

   PTK shall preserve severity, disposition, reason and source location for recognized log findings while leaving process and test outcomes unchanged.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/log_analysis.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sys:: Runtime metadata contract
   :id: REQ_Sys_CONTEXT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: PR fixtures use head identity; exact untagged commits return an empty tag; commit-only templates do not query status/tags or fetch.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_CONTEXT
   :tags: implemented

   PTK shall resolve documented runtime context at execution preparation using local metadata, distinguish source/checkout Git identity, and avoid repeated unnecessary queries.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/git_metadata.py``; ``tests/test_git_metadata.py``.

.. req-sys:: External tool and service contract
   :id: REQ_Sys_TOOLS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Tool/provider/plugin tests demonstrate selection, missing-prerequisite errors and scoped configuration without hard-coded consuming-project names.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_INTEGRATION
   :tags: implemented

   PTK shall select declared tools, credentials and explicitly allowed installed plugins, report unmet prerequisites, and keep project-specific behavior in configuration.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/tools.py``; ``tests/test_tools.py``.

.. req-sys:: Workspace routing contract
   :id: REQ_Sys_VMR
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Git-repo and manual workspace fixtures route member commands, reject alias conflicts and avoid recursive filesystem scanning.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_VMR
   :tags: implemented

   PTK shall discover bounded workspace membership and route a repository alias to its own configuration and output context.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/workspace.py``; ``tests/test_workspace_discovery.py``.

.. req-sys:: Offline authoring contract
   :id: REQ_Sys_AUTHORING
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: An installed wheel can sync resources offline; repeat sync preserves edits and the expert agent references installed resources.
   :verification_level: system-verification
   :req_satisfies: REQ_Stkh_AUTHORING
   :tags: implemented

   PTK shall synchronize version-aligned skills, agent instructions and CLI reference resources into a consuming project without silently overwriting local edits.

   **Origin:** Refinement of the linked stakeholder requirement; review this system-level formulation.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/authoring.py``; ``tests/test_editor_resources.py``.
