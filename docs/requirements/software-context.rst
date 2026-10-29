Runtime context and versioning
==============================

Template values and version identity are resolved by PTK at the appropriate
runtime/build boundary, rather than by the editor.

.. req-sw:: Publish and resolve documented variable namespaces
   :id: REQ_Sw_TEMPLATES
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Catalog tests expose names/help without reading secret values or starting Git; unsupported variable names fail validation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall publish template-variable metadata without resolving secrets and resolve supported runtime namespaces where templating is permitted.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/config/template_variables.py``; ``tests/test_template_variables.py``.

.. req-sw:: Distinguish PR source and checkout commits
   :id: REQ_Sw_PR_SOURCE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: PR and pull_request_target fixtures use the head SHA; missing/invalid metadata fails explicitly; unrelated VMR members ignore the event.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall resolve GitHub PR source commit/branch from valid local head-event metadata and expose the actual checkout commit separately, never substituting a merge/base SHA for missing head identity.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/git_metadata.py``; ``tests/test_git_metadata.py``.

.. req-sw:: Expose short source and checkout hashes
   :id: REQ_Sw_SHORT_COMMIT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Local and PR tests compare both short values with the matching full hashes.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall expose short_commit and short_checkout_commit as the first 12 hexadecimal characters of their corresponding full hashes.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/git_metadata.py``; ``tests/test_git_metadata.py``.

.. req-sw:: Handle exact tags and untagged commits
   :id: REQ_Sw_GIT_TAG
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Annotated/lightweight tag tests and untagged/shallow fixtures return documented values without nearest-ancestor substitution.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall expose sorted exact source tags and select the matching triggering tag or first sorted tag, returning an empty list/string when no exact tag is available.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/git_metadata.py``; ``tests/test_git_metadata.py``.

.. req-sw:: Resolve Git metadata locally and lazily
   :id: REQ_Sw_GIT_LAZY
   :req_type: non-functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Call-count tests prove lazy independent tag/status queries and reuse; a later operation sees changed metadata.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall query Git only when requested, cache results within the operation, and avoid tag/status queries for commit-only templates without fetching or mutating the repository.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/git_metadata.py``; ``tests/test_git_metadata.py``.

.. req-sw:: Capture a shared invocation timestamp
   :id: REQ_Sw_DATES
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Date tests cover timezone rollover, formatting, reports and shared workflow instant; a new invocation captures a new instant.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall capture one instant per CLI invocation and expose local and UTC date fields consistently across job variants and workflow calls.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/config/dates.py``; ``tests/workflows/test_dates.py``.

.. req-sw:: Resolve configured project and component versions
   :id: REQ_Sw_VERSIONS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Versioning tests cover source precedence, dependency validation, generated output and configured fallback failures.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONTEXT
   :tags: implemented

   PTK shall resolve configured version sources and dependencies and expose version context and generated outputs without implicit bump/set/tag operations.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/versioning.py``; ``tests/test_versioning.py``.

.. req-sw:: Freeze source-distribution package version
   :id: REQ_Sw_FROZEN_VERSION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Package tests rebuild an sdist without Git and malformed unrelated configuration does not break minimal package-version resolution.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_DISTRIBUTION
   :tags: implemented

   PTK package builds shall resolve metadata independently of full job configuration and preserve the resolved version when rebuilding a source distribution without Git.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/package_version.py``; ``tests/test_package_version.py``.
