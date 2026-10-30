Logging and reporting
=====================

Canonical results, retained evidence and diagnostic interpretation.

.. req-sw:: Identify console step records by job, variant and step
   :id: REQ_Sw_CONSOLE_PREFIX
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Console and real-process tests verify contextual prefixes, concurrent observer isolation, multiline/tab/control handling, quiet behavior and unchanged captured step text.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall prefix each streamed logical console step line with [variant][job][step],
   matching the output folder order,
   including output, start/finish records and step messages. It shall use the
   selected variant or the established default name when no variant is selected.
   Workspace and cross-repository workflows shall qualify the job field with
   its repository alias while preserving the three-field format.
   Presentation shall preserve tool indentation and keep every logical line
   identifiable without inserting console prefixes into captured step logs.

   **Origin:** Explicit user request for contextual step printouts and consistent
   console indentation. Presentation choices are recorded in :need:`DD_CONSOLE_CONTEXT`.

   **Implementation:** Implemented in the shared console observer. Raw captured
   step text and structured report identities are unchanged. Log layout is
   specified by :need:`REQ_Sw_RUN_HEADERS`.

   **Evidence:** ``tests/test_console_output.py``; ``tests/test_logging.py``;
   ``src/ptk/drivers/cli/console.py``.

.. req-sw:: Show execution hierarchy and prepared metadata in run transcripts
   :id: REQ_Sw_RUN_HEADERS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Observer and real workflow tests verify explicit owner identity, atomic header/summary blocks under concurrency, prepared metadata, verbose variant details, status/count colors, masked values, plain transcripts, cancellation, blocked jobs and permitted failures with exact step identities.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall separate workflow, job and step start/finish records with labelled
   boundaries. Workflow/job headers shall expose prepared project versions,
   variants, run identity and execution limits without additional version
   discovery. Verbose console output shall include resolved variant details.
   Start and summary titles and metadata lines shall repeat their owner context.
   Workspace workflows shall identify workspace scope and list each job's actual
   variant. Header and summary blocks shall remain intact during concurrent
   execution, while step output continues streaming. Job summaries shall list
   steps and workflow summaries shall list job identities and invocation aliases,
   including outcomes, durations, counts and reasons. Execution failure recaps
   shall identify the failed step, or the job if no step result exists, and retain
   permitted failures even when their parent passes.

   PTK shall use purple workflow, cyan job and blue step headings, retain
   independent status colors and provide readable output without color. It
   shall show passed results in green, failed in red, skipped in gray and
   cancelled in amber. Zero counts shall be neutral; allowed failures shall
   retain their failed status with an amber annotation. These presentation
   choices shall not alter execution outcomes. PTK shall write matching
   plain-text aggregate job logs and an immutable workflow
   transcript alongside workflow reports, without adding presentation prefixes
   to raw captured step output or exposing resolved secrets.
   Raw step logs shall use a separate directory so valid step IDs cannot
   overwrite the aggregate job transcript or its metadata.

   **Origin:** Explicit user request for workflow/job/step separation, informative
   headers and consistent extension colors. See :need:`DD_RUN_HIERARCHY`.

   **Implementation:** Shared presentation helpers feed the CLI observer and
   file transcript observers; workflow execution owns the combined transcript.
   The extension applies the same entity roles to tree and editor views.

   **Evidence:** ``tests/test_console_output.py``; ``tests/test_run_summaries.py``;
   ``tests/test_logging.py``;
   ``tests/workflows/test_transcript.py``;
   ``extensions/project-toolkit/test/extension.test.js``;
   ``extensions/project-toolkit/test/graph-editor-ui.test.js``.

.. req-sw:: Use simple reporting and retention defaults
   :id: REQ_Sw_REPORT_DEFAULTS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Default-model and real-run tests produce HTML plus internal run records and retain current plus three previous runs; removed logging/reporting objects fail.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall default report_formats to HTML and logging_history_backups to three, with these logical root fields authored in project.ptk.yml.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/config/model.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Import supported results into one report model
   :id: REQ_Sw_CANONICAL
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Importer fixtures produce typed contributions with expected counts/locations; invalid inputs are reported as problems.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall import JUnit, aggregate Cobertura line coverage, SARIF, log diagnostics and selected contributor output into its canonical report model.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/importers.py``; ``tests/test_reporting.py``.

.. req-sw:: Export supported report formats
   :id: REQ_Sw_EXPORTERS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Exporter tests verify supported content and file results; JUnit represents steps/tests rather than converting log findings into test failures.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall export HTML, JSON, JUnit and Markdown, support GitHub step-summary output when available.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/exporters.py``; ``tests/test_reporting.py``.

.. req-sw:: Retain report inputs and policy per run
   :id: REQ_Sw_REPORT_HISTORY
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: After a subsequent run and policy change, historical/workflow exports retain the prior inputs, logs and dispositions.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall snapshot report inputs, execution context and log-analysis policy for retained runs and workflow children so later exports use the original evidence.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/store.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Recognize supported diagnostic formats
   :id: REQ_Sw_LOG_RECOGNITION
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Positive and negative parser fixtures cover each documented format, command echoes and zero-error summaries.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall recognize documented GCC/Clang, MSVC, CMake, prefixed/bracketed severity, Python-style exception and pytest per-test failure/error summary diagnostics without treating arbitrary occurrences of error/warning as findings or counting pytest traceback lines and aggregate totals again.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/log_analysis.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Apply reasoned ignore and justify rules
   :id: REQ_Sw_LOG_POLICY
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Rule tests cover ordering, scopes, invalid expressions, missing reasons and preserved raw logs.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall apply the first matching configured rule by step, optional severity and message expression, requiring unique IDs and nonblank reasons while retaining the original severity and evidence.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/domain/reporting/log_analysis.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Keep diagnostic disposition separate from failure
   :id: REQ_Sw_LOG_FAILURES
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: A failing command and failing imported test remain failed after matching ignore/justify rules.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall not change command exit status or test outcomes when a diagnostic is ignored or justified.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/report.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Bound analysis to captured visible logs
   :id: REQ_Sw_LOG_BOUNDS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Tests exclude report-disabled steps, reject external/symlink logs and surface oversized-log problems.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK shall analyze only visible recorded step logs within the run directory and report symlink/external or over-50-MiB inputs as problems rather than silently reading them.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/log_analysis.py``; ``tests/reporting/test_log_analysis.py``.

.. req-sw:: Show filterable diagnostic evidence
   :id: REQ_Sw_LOG_HTML
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: HTML/UI checks verify cards, dropdown filters, details, log links and counts on a report fixture.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK HTML reports shall integrate collapsible log analysis with the existing
   failure details, showing log occurrence-count cards and expandable diagnostic
   entries with severity, disposition, step, message, source log/location and
   count, with choice filters for severity and disposition. Log occurrence counts
   shall remain distinct from execution and imported test results. Disabling or
   filtering log analysis shall not hide those failure details.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/log_html.py``; ``scripts/check_report_ui.cjs``.

.. req-sw:: Hide ignored and justified findings initially
   :id: REQ_Sw_LOG_ACTIVE_DEFAULT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: UI checks confirm default/reset active rows and explicit selection of ignored/justified rows with reasons.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_LOGS
   :tags: implemented

   PTK HTML reports shall default disposition filtering to active findings and restore that default when filters are reset while retaining suppressed findings for inspection.

   **Origin:** User decision in the configuration/CLI discussion; this requirement records the agreed behavior.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/adapters/reporting/log_html.py``; ``scripts/check_report_ui.cjs``.

.. req-sw:: Apply report-opening policy locally
   :id: REQ_Sw_OPEN_REPORT
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: under review
   :verification_criteria: Report-opening tests cover always/on-errors/disabled policies, CX behavior and active versus suppressed diagnostics.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall apply configured job/workflow report-opening policy for local runs and account for active log errors without treating suppressed diagnostics alone as an error trigger.

   **Origin:** Derived from the current CLI implementation and regression tests; requires review.

   **Implementation:** Implemented; the following source and tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``src/ptk/application/use_cases/report.py``; ``tests/test_report_open.py``.

.. req-sw:: Inspect recorded execution graphs in reports
   :id: REQ_Sw_REPORT_GRAPHS
   :req_type: functional
   :safety: QM
   :security: false
   :legal: false
   :status: accepted
   :verification_criteria: Job and workflow reports retain recorded joins and outcomes after configuration changes; browser tests open initially collapsed sections, inspect statuses, navigate dependencies and exercise offline zoom, pan, fit and narrow layouts.
   :verification_level: sw-integration-test
   :req_satisfies: REQ_Sys_REPORTS
   :tags: implemented

   PTK shall embed a collapsible dependency diagram, initially closed, in job
   and workflow HTML reports. It shall use recorded run topology and outcomes,
   display shared invocations once with all edges, distinguish passed, failed,
   skipped, cancelled and allowed-failure states using text and colour, and expose
   recorded durations, skip/block reasons and concrete workflow target variants.
   A report-disabled step shall retain only its topology with an explicit hidden
   marker. Diagrams shall work offline and shall not execute commands.

   **Origin:** User request to add collapsible graphs to workflow and job reports.

   **Implementation:** Implemented; the tests are candidate verification evidence, not an acceptance record.

   **Evidence:** ``tests/test_graph_presentation.py``; ``tests/test_report_context.py``;
   ``extensions/project-toolkit/test/graph-ui.test.js``.
