CLI and completion
==================

Command organization, diagnostics, parameter metadata and shell integration.

.. req-sw:: Group commands by purpose
   :id: REQ_Sw_NAMESPACES
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Help, completion and execution agree on command namespaces for ordinary users and maintainers.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall expose permitted jobs and workflows directly, maintenance commands below maintainer, user setup below self-service and project creation as init.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/main.py``; ``tests/test_cli_namespaces.py``.

.. req-sw:: Make validation available without a project
   :id: REQ_Sw_VALIDATE_ALWAYS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Validate succeeds for valid fixtures, reports invalid configuration, and suggests init for missing projects.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall make validate available without a loaded project and, when no marker is found, report no PTK project and suggest init.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/main.py``; ``tests/test_cli_namespaces.py``.

.. req-sw:: Select projects through discovery and routing
   :id: REQ_Sw_NO_CONFIG_OPTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Help omits the removed option; member commands and discovery work without it.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall select projects by working directory and workspace alias rather than exposing a global --config or -C option.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/main.py``; ``tests/test_global_options.py``.

.. req-sw:: Expose typed job parameters
   :id: REQ_Sw_PARAMETERS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Parameter tests cover conversion, choices, invalid values and precedence for concrete variants.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall convert declared job parameters to typed CLI options with help, choices and required/default rules, applying explicit CLI values before file, environment and default values.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/execution/params.py``; ``tests/test_cli_jobs.py``.

.. req-sw:: Suggest contextual option values
   :id: REQ_Sw_VALUE_COMPLETION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Completion and description tests return valid scoped values without executing a job.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall offer eligible variants and step names for variant/from/to options and expose declared choices or help for configured parameters.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/completion.py``; ``tests/test_run_option_metadata.py``.

.. req-sw:: Persist completion in shell profiles
   :id: REQ_Sw_COMPLETION_INSTALL
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Repeated install does not duplicate managed blocks; profile setup does not require an active PTK virtualenv.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_COMPLETION
   :tags: implemented

   PTK shall install idempotent per-user completion hooks for Bash/Git Bash and PowerShell profiles, using the PTK executable resolved by the shell.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/completion_profiles.py``; ``tests/test_completion_profiles.py``.

.. req-sw:: List PowerShell candidates on repeated Tab
   :id: REQ_Sw_SECOND_TAB
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: PowerShell profile/script tests verify the managed Tab handler and native PTK candidate protocol.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_COMPLETION
   :tags: implemented

   PTK shall configure PowerShell completion so an ambiguous completion can list candidates on a second Tab without opening an interactive command prompt replacement.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/completion.py``; ``tests/test_shell_completion.py``.

.. req-sw:: Apply maintainer visibility rules
   :id: REQ_Sw_ACCESS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: An ordinary user cannot execute restricted jobs/workflows even when invoking their names directly.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall use configured maintainer identity to control restricted command visibility and execution consistently across help, completion and description.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/access.py``; ``tests/test_command_access.py``.

.. req-sw:: Diagnose setup prerequisites
   :id: REQ_Sw_DOCTOR
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Doctor tests report available/missing dependencies and remain usable for the supported no-project diagnostic context.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CLI
   :tags: implemented

   PTK shall provide self-service doctor to report host and project prerequisite problems without treating a missing optional editor as a job failure.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/setup.py``; ``tests/test_tools.py``.
