Logging, report formats and log analysis
========================================

Project defaults
----------------

No logging or reporting configuration is required. The logical model has these
root fields, authored in ``project.ptk.yml`` under ``repository.config_path``::

   report_formats: [html]
   logging_history_backups: 3

PTK retains the current run plus three previous runs per variant/job. Zero
backups retains only the current run. Console output defaults to info; use
``-v`` for debug, ``-vv`` for trace and a job's ``--quiet`` for warnings/errors.
Files retain debug information; ``-vv`` also records masked trace information.
Output directories are configured only through ``layout`` in
``folder_structure.ptk.yml``. The old ``logging`` and ``reporting`` objects are
unsupported; there is no legacy fallback.

HTML is the only default exported format. PTK still writes internal ``run.json``
and captured logs for history and later exports. Available exporters are
``html``, ``json``, ``junit``, ``markdown`` and ``github`` (appends Markdown to
``GITHUB_STEP_SUMMARY`` when available).
An empty ``report_formats`` disables full export unless a local
``open_report`` policy requests HTML. The dedicated ``diagnostics.html`` is
always generated and opens for active errors locally, never in CX. Dry runs
do not analyze logs or write reports.

JUnit XML, Cobertura XML (aggregate line coverage), SARIF
supply tool results. Log analysis imports captured step diagnostics. These inputs
feed PTK's canonical report model. HTML integrates log analysis with **What failed**; JSON
retains its structured data, and Markdown/GitHub include its findings. JUnit
exports execution steps and test cases; it does not convert log diagnostics into
failed tests. Report findings never overwrite a process exit code.

Console hierarchy, identity and spacing
----------------------------------------

Real runs use named workflow/job boundaries and compact step records. Start
and summary titles repeat their complete context, for example
``---- JOB [debug][build] | START ----`` and
``---- JOB SUMMARY [debug][build] | FAILED | 2.5s ----``. Workflow titles use
equals signs and ``WORKFLOW``/``WORKFLOW SUMMARY``. Their context is
``[owner-variant][workflow]`` for a repository workflow, or
``[workspace][workflow]`` for a workspace workflow, which has no single variant.
Each metadata line repeats its owner's prefix. Step records use
``[debug][build][compile] STEP | START`` and a matching result line without
another long separator.

Report-link lines repeat the same owner context: for example,
``[debug][build] report: /path/to/report.html`` or
``[debug][verify] report: /path/to/workflow.html``. The prefix uses the owning
job's cyan or workflow's purple color; the path stays literal. Child reports
use the same repository-qualified job identity as their run headers when
needed. Explicit ``report open`` commands identify the saved report's owner
and variant, not a newly selected variant. Workflow summaries save their owner
variant for this purpose; an HTML-only workflow report still shows its workflow
name when that metadata is unavailable.

Entity labels, separators and metadata prefixes are purple for workflows,
cyan for jobs and blue for steps. A failed job's title stays cyan while its
``FAILED`` outcome is red. ``PASSED`` is green, ``SKIPPED`` gray and
``CANCELLED`` amber. Nonzero status counts use the corresponding color;
zero counts are neutral. An allowed failure remains ``FAILED`` with an amber
``allowed failure`` annotation. Labels and reasons remain visible without
color. Terminal and VS Code themes choose the exact shades. The extension
uses the same entity colors and neutral gray for built-in commands.

The workflow header shows its owner or workspace, PTK version, run ID, job count
and concurrency limit. It lists the participating repositories' project names,
resolved project versions and selected variants. Each job header shows its
project and repository, project/PTK versions, variant name and description,
component/feature counts, run ID, step count and concurrency limit. Workflow
jobs also identify the workflow and invocation. An unconfigured project version
is shown as ``not configured``; an absent variant model is shown as
``default (no variant model)``. Headers reuse prepared, masked metadata without
performing additional version discovery. Use ``-v`` to include variant
inheritance, selected components and resolved feature values on the console.

Step starts include the command, optional display title and requested generators.
Step finishes show outcome, duration and an available failure/skip reason.
A skipped step's duration is a dash because it did not execute. Job/workflow
summary titles retain their measured duration even when all children skipped.
Job summaries list each step's ID, result, duration and reason. Workflow
summaries list jobs with their actual variants, repository qualification where
needed and invocation aliases, including jobs blocked before they could start.
Both include colored status counts and the log location.

``What failed`` recap lines identify failed execution steps using their complete
``[variant][job][step]`` identity. A failure before step execution identifies the
job instead. Allowed failures remain visible, including when the enclosing job
or workflow passes. A workflow summary annotates failures permitted by its
invocation policy. Cancellation and skips retain their reasons without being
relabeled as failures. This recap uses execution results; detailed imported
test/log diagnostics remain in the HTML report. A passed job with report errors
is marked ``report findings (see report)`` in the workflow summary.

PTK prefixes step output, start/finish records and step messages with
``[variant][job][step]``, matching the output folder order. For example, the
documentation job prints ``[default][docs][sphinx]``. These are the job and step
IDs, not display titles or workflow invocation aliases. ``default`` is the
existing no-variant convention; a selected variant uses its own name.
Job-level messages use ``[variant][job]``.
Each concurrent job retains its own context. Workspace and cross-repository
workflows qualify the job field as ``[variant][repository:job][step]`` to
distinguish equal job IDs while preserving three fields. Invocation aliases
appear in job metadata and the workflow summary.

Each header with its metadata, and each complete summary, is written as one
block. Parallel jobs continue streaming between blocks; they are not buffered
until completion. PTK does not
increase indentation with nesting. The prefix identifies the emitting step
even when several jobs have started since its header.

Every streamed logical line receives a prefix, including multiline messages.
Tabs expand to eight-column stops within the tool text before PTK adds the prefix, preserving
the tool's indentation independently of identifier lengths. Tool ANSI colors
are interpreted; cursor movement and erase controls do not redraw the shared
console. Carriage-return progress updates become separate lines.

Streaming prefixes are unpadded; summary columns align within their own block.
PTK does not reflow captured output.
Long lines may wrap at the terminal's current width, with wrapped continuations
starting at the terminal margin. Captured step logs retain their original text
without these console prefixes or presentation changes. The aggregate job
``run.log`` and workflow ``workflow.log`` contain the same boundaries and
contextual records as plain text, with timestamps and file-level debug detail.
Raw step logs live at ``_logs/VARIANT/JOB/steps/STEP.log``, separate from the
job's ``run.log`` and metadata. This prevents a valid step named ``run`` from
overwriting the job transcript. Use ``${run.log_file}`` or
``${steps.ID.log_file}`` in steps to obtain the declared step log path.
The workflow log lives alongside its immutable workflow reports and combines
child job output as it arrives. See :doc:`workflows`, :need:`DD_CONSOLE_CONTEXT`,
:need:`DD_RUN_HIERARCHY`, :need:`REQ_Sw_CONSOLE_PREFIX` and
:need:`REQ_Sw_RUN_HEADERS`.

Recognition and rules
----------------------

Log analysis is enabled by default. Set ``log_analysis.enabled: false`` to disable
it. It recognizes GCC/Clang file:line diagnostics, MSVC file(line) diagnostics,
CMake error/warning headers, prefixed ``ERROR:``/``WARNING:`` and bracketed
``[ERROR]``/``[WARNING]``/``[WARN]`` messages, Python-style exception messages,
and pytest's per-test ``FAILED``/``ERROR`` summary lines (including collection
errors). Pytest traceback assertion lines and aggregate totals are not counted
again. JUnit remains the source of structured test counts and failure details;
log recognition does not create additional test cases.
It does not classify arbitrary text merely containing "error", command echoes,
PTK log envelopes or summaries such as "0 errors". Unrecognized output remains
available in the original log; no findings does not prove a successful run.

Rules are optional and belong in ``project.ptk.yml``::

   log_analysis:
     enabled: true
     rules:
       - id: deprecated-sdk
         match:
           step: compile
           severity: warning
           message_regex: 'SDK function .* is deprecated'
         action: justify
         reason: Required until the SDK upgrade.
       - id: expected-negative-test
         match:
           step: negative-tests
           severity: error
           message_regex: '^expected invalid input$'
         action: ignore
         reason: Intentional diagnostic from negative tests.

Rules have unique IDs and nonblank reasons. All match conditions must match;
step is a case-sensitive glob over the complete step path, severity is optional,
and the regular expression searches the diagnostic message without its severity
prefix. First matching rule wins. Invalid expressions fail configuration
validation. ``ignore`` marks expected noise; ``justify`` records an accepted
finding. Both retain the original severity, source log, line and reason. Neither
modifies raw logs or changes execution/test failures. Active errors automatically open the dedicated diagnostics report locally;
suppressed imported diagnostics do not trigger it on their own. These same
rules also apply to CMake, Bazel, SARIF, JUnit failure/error messages and Sphinx-Needs
violations, even when console log analysis is disabled. Imported test statuses
and totals remain factual; suppression changes diagnostic disposition only.
Execution failures and report-collection problems remain visible.

The rule policy is captured when the run is prepared and saved in ``run.json``.
Changing configuration does not reinterpret archived runs with today's rules.
Historical exports use archived logs; workflow child reports use retained log
copies. A step marked ``report: false`` is excluded from analysis as well as
other report imports. Current and historical reports remain read-only records.

Analysis is local and bounded to recorded step logs inside the recorded run
log directory. Symlinked/external files and files larger than 50 MiB produce a
report problem instead of being silently read or partially analyzed. ANSI
colors are stripped for recognition and display; captured logs are unchanged.
Repeated identical diagnostics in the same step/log and source location are
grouped, retaining an occurrence count and the first 50 log line numbers.
Surrounding context is retained for the first occurrence. No AI service or
network request is involved in deterministic analysis.

HTML interaction
-----------------

**What failed** lists active errors with source and owner, linking to detailed
execution, test, static-analysis, log or report-collection evidence. The
**Diagnostics** section provides one expandable presentation with source,
severity, disposition, owner and step filters plus text search. Disabling log
analysis never removes execution or imported test failures.

Log cards show active error/warning occurrences and justified/ignored
occurrences. These are not failed-test counts. Clicking a card selects log
analysis as the source and applies the corresponding severity/disposition.
Counts describe the whole run and do not change when filtering. Active is the
default disposition; reset restores active findings across all sources. Failure
links reveal their target even when current filters would hide it.

Expanded log entries show context with matching lines highlighted, source-log
links, location, tool/rule and disposition reason. Search matches the diagnostic's
message and metadata rather than unrelated neighboring context lines. Reports
retain relative links to captured logs or historical copies. An empty log
analysis means no recognized active diagnostics, not proof that execution or
imported tests passed. See :doc:`reports` for report navigation and expandable
workflow graphs.

Assistant support
------------------

``ptk maintainer sync agent`` distributes ``ptk-log-analyzer`` and the
``ptk-expert`` custom agent alongside the other PTK authoring skills. In clients
supporting GitHub custom agents, select **ptk-expert**. It routes requests to the
relevant skill and starts diagnostics from existing reports/logs. It does not
automatically rerun jobs, hide errors or justify findings without evidence.
