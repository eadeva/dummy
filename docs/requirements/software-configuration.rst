Configuration and workspaces
============================

Discovery, file ownership, schema authority and workspace routing.

.. req-sw:: Discover the project marker
   :id: REQ_Sw_DISCOVERY_MARKER
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Nested invocation finds the owning project; missing and malformed markers produce different diagnostics.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall search upward for .main.ptk.yml without crossing a Git repository boundary and distinguish a missing marker from a malformed marker.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/project.py``; ``tests/test_workspace_discovery.py``.

.. req-sw:: Load only owned conventional documents
   :id: REQ_Sw_FIXED_LAYOUT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Known documents load; arbitrary filenames and nested entity fragments fail; unrelated repository files are not scanned.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall load the documented section files and direct named files in variants, jobs and workflows under repository.config_path, rejecting unsupported PTK filenames in those owned locations.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/config/discovery.py``; ``tests/test_fixed_config.py``.

.. req-sw:: Reject removed configuration forms
   :id: REQ_Sw_NO_LEGACY
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Fixtures using removed forms fail validation and do not produce a silently converted project.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall reject include chains, obsolete schema fields and legacy loading forms instead of migrating or applying a fallback loader.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/config/model.py``; ``tests/test_fixed_config.py``.

.. req-sw:: Keep one owner per configuration entity
   :id: REQ_Sw_SECTION_OWNERSHIP
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: A job document containing an assembled-root object fails; the same job name cannot be split across documents.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall derive a named entity from its conventional filename and accept only the corresponding section body, with the root marker restricted to repository metadata.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/config/source.py``; ``tests/test_fixed_config.py``.

.. req-sw:: Read component variants beside component code
   :id: REQ_Sw_COMPONENT_LOCAL
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Registered local definitions contribute features; missing optional documents give empty components; duplicates and unsafe paths fail.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall read component.variants.ptk.yml only from registered component directories inside the repository and reject duplicate registrations and symlink/escaping paths.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/config/discovery.py``; ``tests/test_fixed_config.py``.

.. req-sw:: Preserve source-aware validation errors
   :id: REQ_Sw_SOURCE_ERRORS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Invalid documents and unresolved references fail with the owning file/location and configuration path where available.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall retain source locations during composition and report invalid values and cross-document references with actionable diagnostics.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/config/yaml_loader.py``; ``tests/unit/test_loader.py``.

.. req-sw:: Apply explicit value overrides
   :id: REQ_Sw_OVERRIDES
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Explicit override tests change the effective value without changing files; unknown or invalid overrides fail validation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall retain explicit --set overrides, shared job defaults and declared variant inheritance while keeping file precedence absent.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/project.py``; ``tests/test_fixed_config.py``.

.. req-sw:: Export CLI-owned schema and inventory
   :id: REQ_Sw_SCHEMA_AUTHORITY
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Configuration description tests compare inventory and file ownership against the CLI loaded model, including invalid and missing projects.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall export configuration schemas, ownership, provenance, validation errors and parameter metadata from its own loading and model mechanisms for external consumers.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/editor.py``; ``tests/test_editor_inventory.py``.

.. req-sw:: Initialize without replacing existing files
   :id: REQ_Sw_INIT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Noninteractive init without a config directory fails; successful init validates; repeated init and dry-run preserve existing files.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall require an explicit or interactively supplied configuration directory for init and scaffold conventional files without overwriting existing configuration.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/init.py``; ``tests/test_init.py``.

.. req-sw:: Discover bounded workspace membership
   :id: REQ_Sw_VMR_DISCOVERY
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Missing indexes, nested member pointers, unrelated repositories and explicit opt-out fixtures have the documented discovery outcomes.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_VMR
   :tags: implemented

   PTK shall use the git-repo member index or a manual workspace marker with explicit members/direct children and shall not recursively discover arbitrary repositories.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/workspace.py``; ``tests/test_workspace_discovery.py``.

.. req-sw:: Route each member independently
   :id: REQ_Sw_VMR_ROUTING
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Commands for two members retain separate configurations and outputs; bare workspace invocation lists members without running them all.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_VMR
   :tags: implemented

   PTK shall execute a workspace repository alias with that member's own project, tools, permissions, credentials and output context.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/workspace.py``; ``tests/test_workspace.py``.

.. req-sw:: Initialize unconfigured workspace members
   :id: REQ_Sw_VMR_INIT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Batch dry-run writes nothing; conflicting fragments block preflight; repeat initialization skips completed members.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_VMR
   :tags: implemented

   PTK shall initialize checked-out members lacking a marker, preflight all new scaffolds, and skip existing markers and missing checkouts with a summary.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/init.py``; ``tests/test_workspace_init.py``.

.. req-sw:: Select component-owned features by qualified identity
   :id: REQ_Sw_COMPONENT_SELECTIONS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Two components may declare the same local feature name; product selections, inheritance, expressions and CLI overrides resolve independently; invalid types, unknown references and exported-name collisions fail.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_CONFIG
   :tags: implemented

   PTK shall load reusable component feature declarations from PTK YAML and use
   component.FEATURE as their identity in product variant selections, conditions
   and overrides. It shall validate and resolve defaults, types, ranges, enum
   choices, dependencies and constraints before executing a generator. It shall
   reject ambiguous uppercase export names and removed unqualified selection forms.

   **Origin:** Accepted user counterproposal to the other team's CMake-owned
   feature declarations, motivated by reuse across build tools.

   **Implementation:** Implemented. Components declare possibilities; products
   select values; project code owns target/compiler behavior.

   **Evidence:** ``src/ptk/domain/variants/model.py``;
   ``src/ptk/domain/variants/rules.py``; ``tests/unit/test_variants.py``;
   ``tests/test_variant_commands.py``; ``tests/test_step_generators.py``.
