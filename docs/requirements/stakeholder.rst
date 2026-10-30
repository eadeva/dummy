Stakeholder requirements
========================

These needs record explicit user decisions and consolidated existing capabilities.
New implementation-derived needs remain ``new/changed``. Feature groupings are
organizational, not requirements or implementation statuses.

.. feature:: Predictable project configuration
   :id: FEAT_CONFIG

   Grouping for the associated PTK stakeholder needs.

.. feature:: Repeatable job execution
   :id: FEAT_EXECUTION

   Grouping for the associated PTK stakeholder needs.

.. feature:: Discoverable command-line interface
   :id: FEAT_USABILITY

   Grouping for the associated PTK stakeholder needs.

.. feature:: Team distribution and self-service
   :id: FEAT_DISTRIBUTION

   Grouping for the associated PTK stakeholder needs.

.. feature:: Diagnosable execution results
   :id: FEAT_RESULTS

   Grouping for the associated PTK stakeholder needs.

.. feature:: Project and tool integration
   :id: FEAT_INTEGRATION

   Grouping for the associated PTK stakeholder needs.

.. feature:: Version-aligned project authoring
   :id: FEAT_AUTHORING

   Grouping for the associated PTK stakeholder needs.


.. req-stkh:: Conventional project configuration
   :id: REQ_Stkh_CONFIG
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_CONFIG
   :tags: implemented

   PTK shall organize configuration through known files and explicit ownership, retaining the .main.ptk.yml marker and keeping component feature definitions beside their component code.

   **Origin:** Accepted replacement of decentralized loading and include chains.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Minimal and discoverable CLI
   :id: REQ_Stkh_CLI
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_USABILITY
   :tags: implemented

   PTK shall expose project jobs and workflows directly, group maintainer operations under maintainer, and group user installation/setup operations under self-service while keeping init separate.

   **Origin:** Accepted command-group simplification.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Persistent user completion
   :id: REQ_Stkh_COMPLETION
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_USABILITY
   :tags: implemented

   PTK shall provide persistent per-user completion for PowerShell and Bash, including Git Bash on Windows, with command, option and contextual value suggestions.

   **Origin:** Accepted completion discussion; per-user installation replaced the initial machine-wide request.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Run multiple selected variants
   :id: REQ_Stkh_VARIANTS
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_EXECUTION
   :tags: implemented

   PTK shall allow a job to run for several selected variants in parallel and preserve variant selection for workflow calls.

   **Origin:** Accepted request to support multichoice job variants and workflows.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Consistent execution contexts
   :id: REQ_Stkh_EXECUTION
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: new/changed
   :safety_relevance: no
   :clustered_by: FEAT_EXECUTION
   :tags: implemented

   PTK shall provide reusable configured jobs with typed inputs, selected tools and controlled execution environments.

   **Origin:** Consolidated requirement derived from current execution capabilities; review the detailed software requirements.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Distribute matching artifacts
   :id: REQ_Stkh_DISTRIBUTION
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_DISTRIBUTION
   :tags: implemented

   PTK shall distribute its Python package, installer and matching editor artifact so team members can install and configure them without building the editor themselves.

   **Origin:** Accepted proposal to bundle the VSIX as a Python package resource.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Preserve newer PTK installations
   :id: REQ_Stkh_KEEP_NEWER
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_DISTRIBUTION
   :tags: planned

   PTK installers shall retain a newer installed PTK Python package when asked to install an older version.

   **Origin:** Accepted installation simplification request; implementation remains outstanding.

   **Implementation:** Not implemented. No passing verification result is claimed.

.. req-stkh:: Explain failures through reports
   :id: REQ_Stkh_RESULTS
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_RESULTS
   :tags: implemented

   PTK shall import supported execution/tool results into a canonical model and export reports that preserve the evidence needed to diagnose failures.

   **Origin:** Accepted reporting/importer/exporter discussion.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Review and classify log diagnostics
   :id: REQ_Stkh_LOG_ANALYSIS
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_RESULTS
   :tags: implemented

   PTK shall identify warning/error diagnostics, support reasoned ignore/justify policies and show filterable findings with source logs in HTML reports.

   **Origin:** Accepted log-analysis and HTML presentation requests.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Expose useful runtime context
   :id: REQ_Stkh_CONTEXT
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_INTEGRATION
   :tags: implemented

   PTK shall provide documented built-in template values, including source Git identity, a short commit hash, exact tag values and environment variables, without unnecessary Git queries.

   **Origin:** Accepted runtime-variable and Git performance discussion.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Integrate existing project tools
   :id: REQ_Stkh_INTEGRATION
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: new/changed
   :safety_relevance: no
   :clustered_by: FEAT_INTEGRATION
   :tags: implemented

   PTK shall support project tools, credentials, build generators, artifact destinations and ordinary Python tools through declared configuration.

   **Origin:** Derived from the present public CLI and configuration model; stakeholder review remains required.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Keep workspace members independent
   :id: REQ_Stkh_VMR
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_INTEGRATION
   :tags: implemented

   PTK shall route virtual-monorepo commands to independently configured repositories using automatic bounded discovery rather than a required global configuration-path option.

   **Origin:** Accepted VMR discovery discussion; detailed routing is implementation-derived.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

.. req-stkh:: Keep authoring knowledge version aligned
   :id: REQ_Stkh_AUTHORING
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: accepted
   :safety_relevance: no
   :clustered_by: FEAT_AUTHORING
   :tags: implemented

   PTK shall provide an expert agent and task-specific skills, including log analysis, using the installed CLI and project context rather than assumptions about PTK's own repository.

   **Origin:** Accepted authoring-agent, skill review and independence requests.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.
