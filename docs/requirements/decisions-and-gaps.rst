Open work and superseded decisions
==================================

The accepted package-downgrade guard is not implemented:
:need:`REQ_Sw_KEEP_NEWER_PACKAGE`. Native CI generation remains a draft proposal:
:need:`REQ_Sw_CI_GENERATION`. Neither is covered by a claimed passing result.

Most implementation-derived requirements remain under review. This is a review
backlog, not proof that their behavior is absent. External/native platform
verification is limited to the environments actually exercised.

The records below preserve changed decisions. They do not authorize legacy
loading, include support, global configuration overrides or machine-wide shell
profile changes. Per-user completion is the accepted scope.

.. req-stkh:: Discover arbitrary decentralized fragments
   :id: REQ_Stkh_DECENTRALIZED
   :req_type: stakeholder technical requirement
   :safety: QM
   :security: false
   :legal: false
   :status_crs: obsolete
   :safety_relevance: no
   :clustered_by: FEAT_CONFIG
   :tags: superseded

   PTK would discover all repository ``*.ptk.yml`` fragments and combine them without include directives.

   **Origin:** Earlier accepted idea explicitly replaced by the fixed conventional layout and component-local definitions; superseded by REQ_Stkh_CONFIG.

   **Implementation:** Superseded; retained only to explain the changed decision.

.. req-sw:: Expose a global configuration path override
   :id: REQ_Sw_CONFIG_OVERRIDE
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: obsolete
   :verification_criteria: Historical only; current CLI tests verify the option is absent and automatic discovery/routing is used.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Stkh_VMR
   :tags: superseded

   PTK would expose or hide a global --config option to select the project configuration file.

   **Origin:** Earlier command-option discussion was superseded by project discovery and alias routing; see REQ_Sw_NO_CONFIG_OPTION.

   **Implementation:** Superseded; retained only to explain the changed decision.

   **Evidence:** ``tests/test_global_options.py``.
