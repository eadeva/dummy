Tools and integrations
======================

Configured external dependencies, trusted plugin contracts and maintenance.

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

.. req-sw:: Load only explicitly selected plugins
   :id: REQ_Sw_PLUGINS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Plugin tests cover all supported entry-point groups, disabled distributions and invalid registrations.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_TOOLS
   :tags: implemented

   PTK shall discover installed distributions named in project configuration and reject missing, duplicate, reserved or non-callable registrations without implicitly installing plugins.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/plugins.py``; ``tests/test_plugins.py``.

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
