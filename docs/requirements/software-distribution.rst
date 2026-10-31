Distribution and project authoring
===================================

Packaging, current-user setup and version-aligned authoring resources. Planned
items are explicitly marked and must not be presented as supported commands.

.. req-sw:: Bundle the prepared matching editor artifact
   :id: REQ_Sw_BUNDLE_VSIX
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Wheel/sdist tests verify bundled version metadata and installation source; a missing prepared artifact fails the release build.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_DISTRIBUTION
   :tags: implemented

   PTK release preparation shall bundle the matching VSIX in the Python package so self-service extension can install it without rebuilding from source.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/extension_bundle.py``; ``tests/test_package_build.py``.

.. req-sw:: Orchestrate per-user setup after installation
   :id: REQ_Sw_INSTALL_SETUP
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Installer tests cover local/package/archive sources, failed installation and subsequent setup invocation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_DISTRIBUTION
   :tags: implemented

   PTK installers shall install the selected Python source and then invoke supported completion and optional editor setup, reporting installation failure instead of claiming success.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``install/install.ps1``; ``tests/test_install_scripts.py``.

.. req-sw:: Preserve a newer editor extension
   :id: REQ_Sw_EXTENSION_VERSION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Extension installation tests cover older/equal/newer bundled versions and explicit force.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_DISTRIBUTION
   :tags: implemented

   PTK self-service extension shall preserve an installed newer extension unless replacement is explicitly forced.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/drivers/cli/extension.py``; ``tests/test_extension_installation.py``.

.. req-sw:: Prevent unintended Python-package downgrade
   :id: REQ_Sw_KEEP_NEWER_PACKAGE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: An installed newer package survives selection of an older release, wheel/archive and local source; equal/newer selections still refresh as intended.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_UPGRADE
   :tags: planned

   PTK installers shall compare the installed and selected PTK Python package versions and retain the installed package when it is newer, across supported package sources.

   **Origin:** Accepted user request to keep the newest installed PTK; current installers still refresh the selected source and no package downgrade guard is implemented.

   **Implementation:** Not implemented. No passing verification result is claimed.

   **Evidence:** ``install/install.ps1``.

.. req-sw:: Prepare artifacts without publishing
   :id: REQ_Sw_PACKAGE_PREPARATION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Package-preparation tests validate staged artifact names/metadata and installed-wheel smoke checks without publish operations.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_DISTRIBUTION
   :tags: implemented

   PTK package preparation shall validate the sdist/wheel, documentation and editor artifact and stage a manifest without uploading, tagging or publishing.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``scripts/prepare_package.py``; ``tests/test_package_preparation.py``.

.. req-sw:: Synchronize an expert agent and task skills
   :id: REQ_Sw_AGENT_SYNC
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Installed-resource tests verify agent/skill references and offline docs in a separate consuming project.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_AUTHORING
   :tags: implemented

   PTK maintainer sync agent shall distribute the expert agent, project-facing skills including log analysis, offline references and examples from the installed package.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/authoring.py``; ``tests/test_editor_resources.py``.

.. req-sw:: Preserve local authoring-resource edits
   :id: REQ_Sw_SYNC_PROTECTION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Sync tests distinguish unchanged managed files, modified files, stale managed files and explicit force behavior.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_AUTHORING
   :tags: implemented

   PTK shall track synchronized resources and preserve local changes on repeat sync unless an explicit force update is requested.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/authoring.py``; ``tests/test_editor_resources.py``.

.. req-sw:: Keep distributed skills project independent
   :id: REQ_Sw_PROJECT_INDEPENDENCE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Catalog/resource checks reject broken checkout-only links and exercise installed authoring resources in a separate project.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_AUTHORING
   :tags: implemented

   PTK distributed skills shall obtain current commands and configuration from the consuming project and installed CLI and shall not require PTK's own development tree.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/authoring_bundle.py``; ``tests/test_authoring_skills.py``.

.. req-sw:: Generate native CX workflow files
   :id: REQ_Sw_CI_GENERATION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Integration tests generate the real verify graph, verify setup and producer needs, per-variant selectors, callable-only Docker inputs, VMR checkout TODOs, maintainer access and repeated-generation preservation.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_EXECUTION
   :tags: implemented

   PTK shall generate commented callable GitHub workflows in the owning
   repository's .github/workflows directory. Setup shall run the matrix command
   first; every execution job shall depend on it and its configured producers,
   download producer outputs, run one PTK job and upload available outputs.
   Generation shall never overwrite existing files and shall warn instead.
   Runner selection, Docker images and caller events remain project TODOs.
   A detected VMR shall replace normal checkout with VMR checkout TODOs.

   **Origin:** User request for built-in Actions and almost-finished workflow
   templates, with setup matrix dependencies and VMR-specific checkout.

   **Implementation:** Implemented; see :doc:`/guides/github-actions` for limits.
   No remote workflow execution is implied by generation.

   **Evidence:** ``src/ptk/drivers/cli/github_workflows.py``;
   ``tests/test_github_actions.py``; ``.github/workflows/ptk-verify.yml``.
