Tools and integrations
======================

Configured external dependencies, ordinary Python tools and maintenance.

.. req-sw:: Check and provision declared tools
   :id: REQ_Sw_TOOLS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Tool tests cover version constraints, missing tools, installer errors and refreshed executable paths.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall check declared tool versions, provision through configured supported sources/installers when explicitly requested, and recheck availability after installation.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/tools.py``; ``tests/test_tools.py``.

.. req-sw:: Resolve configured credential providers
   :id: REQ_Sw_CREDENTIALS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Provider tests cover environment/vault/keyring or mocked optional stores, unavailable providers and masked output without revealing stored values.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall provision and resolve declared credentials through supported providers and mask known secret values in its logging path.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/credentials.py``; ``tests/test_credentials.py``.

.. req-sw:: Scope workspace credential storage
   :id: REQ_Sw_CREDENTIAL_SCOPE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Workspace credential tests prevent conflicting definitions from overwriting each other and preserve explicit provider mappings.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_VMR
   :tags: implemented

   PTK shall combine identical workspace credential definitions, disambiguate conflicts, and namespace storage by definition/workspace unless an explicit namespace is provided.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/credentials.py``; ``tests/test_workspace.py``.

.. req-sw:: Generate build-system variant files
   :id: REQ_Sw_GENERATORS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Generator tests validate escaping, output confinement and collisions; native Make/CMake/GN consumers and Bazel settings/changed-snapshot tests pass on the recorded tool versions.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall provide header, CMake, Bazel, Make, GN, Yocto, Robot and Sphinx variant generators using uppercase VARIANT_<COMPONENT>_<FEATURE> symbols and step-local output files. Bazel shall receive schema-versioned JSON; its optional repository helper shall be a project-owned documentation resource outside PTK runtime. GN shall receive a .gni file, not plain Ninja rules.

   **Origin:** Accepted reusable-component counterproposal and explicit Make/CMake/Bazel/GN integration request.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/variants/generators.py``; ``tests/test_generators.py``; ``tests/test_native_variant_builds.py``; ``docs/resources/bazel/ptk_variants.bzl``.

   Native GN/Bazel tests require their documented executable variables. Skipped
   native tests are not evidence of compatibility on that environment.

.. req-sw:: Resolve configured artifact destinations
   :id: REQ_Sw_ARTIFACT_PATHS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Destination tests cover substitution and ownership; invalid destination rules fail without unintended operations.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall resolve configured artifact destination paths from runtime context and execute only explicitly requested artifact operations.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/artifacts.py``; ``tests/test_artifact_destinations.py``.

.. req-sw:: Synchronize declared shared tool configuration
   :id: REQ_Sw_SHARED_CONFIG
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Shared-config tests verify composition, repeat sync and detection of stale generated files.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall compose supported shared tool defaults and explicit repository overlays into generated files and expose drift validation.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/configs.py``; ``tests/test_shared_configs.py``.

.. req-sw:: Manage repository hooks explicitly
   :id: REQ_Sw_HOOKS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Hook tests use temporary Git repositories to verify installation, failure blocking and sanitized environment behavior.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall expose hook install/uninstall/status and apply configured local hook setup without leaking PTK virtualenv selectors into hook commands.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/hooks.py``; ``tests/hooks/test_installation.py``.

.. req-sw:: Run reusable Python tools without a third-party PTK plugin API
   :id: REQ_Sw_EXTERNAL_TOOLS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: A built ordinary wheel executes through PTK and uv with correct success/failure status; retired plugin settings and custom hook names produce editable configuration errors; installed PTK entry points are never discovered or imported; supported built-ins remain available.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall execute reusable Python tools through its normal command/Python modes
   and shall not discover or load third-party PTK entry points. It shall reject
   removed plugins/custom installers fields and unsupported operation, generator,
   provider and report-format names through normal configuration validation.
   It shall retain its shipped integrations and editable invalid configuration.

   **Origin:** Explicit user decision to remove plugin complexity and Python API
   version coupling in favor of ordinary packages distributed through Artifactory
   and executed with uv. PTK has not been rolled out; no migration code, legacy
   implementation or fallback behavior shall be retained.

   **Implementation:** Implemented; compatibility is defined by CLI/configuration
   and documented data contracts, not public PTK Python callbacks. Project tools
   remain responsible for their own dependencies, side effects and versioning.

   **Evidence:** ``tests/test_no_plugins.py``;
   ``tests/test_python_tool_package.py``; ``tests/test_step_generators.py``;
   ``extensions/project-toolkit/test/integration.test.js``;
   ``src/ptk/domain/config/model.py``; :need:`DD_NO_PLUGIN_API`.
