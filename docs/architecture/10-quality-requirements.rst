Quality requirements
====================

Quality scenarios describe observable expectations without inventing unsupported
latency or throughput targets. Numerical service-level targets remain a future
stakeholder decision.

.. list-table:: Quality scenarios and evidence
   :header-rows: 1
   :widths: 20 45 35

   * - Quality
     - Stimulus and expected response
     - Evidence / limit
   * - Diagnosability
     - A conventional file contains an invalid value; validation identifies its source and fails before execution.
     - Loader/model tests and :need:`REQ_Sw_SOURCE_ERRORS`.
   * - Responsiveness
     - A template uses only a commit hash; PTK avoids tag/worktree queries and reuses resolved metadata within the operation.
     - Git call-count tests; :need:`REQ_Sw_GIT_LAZY`. No universal wall-clock guarantee.
   * - Portability
     - A supported job runs in a path containing spaces on Linux or Windows with correct arguments and cancellation.
     - Native process and quickstart tests in the CI matrix; host-specific tools remain prerequisites.
   * - Reproducibility
     - A historical report is exported after another run; its inputs and diagnostic policy remain those of the selected run.
     - Reporting/history tests; :need:`REQ_Sw_REPORT_HISTORY`.
   * - Predictability
     - An unsupported configuration file is added; loading rejects it rather than selecting an implicit winner.
     - Fixed-layout tests; :need:`REQ_Sw_FIXED_LAYOUT`.
   * - Recoverability
     - A repeated resource sync encounters a local edit; it preserves that edit unless an explicit overwrite is requested.
     - Authoring resource tests; :need:`REQ_Sw_SYNC_PROTECTION`.

Performance measurements and their reproducibility limits are documented in
:doc:`/guides/performance`. Read-count assertions test bounded discovery and
cache behavior without fragile timing thresholds. Measurements on one machine
are observations, not product-wide performance commitments.
