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
An empty ``report_formats`` disables automatic export unless a local
``open_report`` policy requests HTML. Existing job/workflow opening policies
remain unchanged. Dry runs do not analyze logs or write reports.

JUnit XML, Cobertura XML (aggregate line coverage), SARIF
supply tool results. Log analysis imports captured step diagnostics. These inputs
feed PTK's canonical report model. HTML integrates log analysis with **What failed**; JSON
retains its structured data, and Markdown/GitHub include its findings. JUnit
exports execution steps and test cases; it does not convert log diagnostics into
failed tests. Report findings never overwrite a process exit code.

Console hierarchy, identity and spacing
----------------------------------------

Real runs print start and finish boundaries for each execution level:
``======== WORKFLOW``, ``-------- JOB`` and ``--- STEP``. Workflow headings
are purple, job headings cyan and step headings blue. Outcome words retain
their status colors (green passed, red failed, yellow cancelled); labels also
identify the level and outcome when color is unavailable. Terminal and VS Code
themes choose the exact shades. The extension uses the same entity colors and
neutral gray for built-in commands.

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
Job/workflow footers give outcome, duration, status counts and log location;
workflow footers also list individual invocations, including jobs blocked before
they could start. An allowed failure is explicitly labelled.

PTK prefixes step output, start/finish records and step messages with
``[job][variant][step]``. For example, the documentation job prints
``[docs][default][sphinx]``. These are the job and step IDs, not display titles or
workflow invocation aliases. ``default`` is the existing no-variant convention;
a selected variant uses its own name. Job-level messages use ``[job][variant]``.
Each concurrent job retains its own context. Workspace and cross-repository
workflows qualify the first field as ``[repository:job][variant][step]`` to
distinguish equal job IDs while preserving three fields. Invocation aliases
appear in job metadata and the workflow summary.

Each header and its metadata are written as one block. Parallel jobs continue
streaming between blocks; they are not buffered until completion. PTK does not
increase indentation with nesting. The prefix identifies the emitting step
even when several jobs have started since its header.

Every logical line receives a prefix, including multiline messages. Tabs expand
to eight-column stops within the tool text before PTK adds the prefix, preserving
the tool's indentation independently of identifier lengths. Tool ANSI colors
are interpreted; cursor movement and erase controls do not redraw the shared
console. Carriage-return progress updates become separate lines.

PTK does not pad identifiers into fixed-width columns or reflow captured output.
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
modifies raw logs or changes execution/test failures. Active log errors can
trigger existing ``open_report: on_errors`` behavior; suppressed diagnostics do
not trigger it on their own.

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

**What failed** brings execution failures, imported test failures and report
problems together with a collapsible **Log analysis** view. The existing failure
details stay visible; log analysis starts collapsed when these details exist,
and expanded under **Diagnostics** otherwise. Disabling log analysis still leaves
execution and imported test failures visible.

Log analysis has cards for active log errors, active log warnings, justified log
findings and ignored log findings. These counts cover recognized log occurrences
only, not failed tests or failed steps. A test failure may also appear in its
captured log; these are two views of the evidence, not additional test failures.
Clicking a card sets the severity/disposition filters. Counts describe the whole
run and do not change when filtering.

Each diagnostic is an expandable entry showing severity, disposition, step,
message/details, source-log filename, source location (or log line) and occurrence
count. Severity and disposition have choice dropdowns. **Active** is the default disposition,
so justified and ignored findings start hidden. Step filtering and search combine
with those choices. **Reset filters** restores all severities, active findings,
all steps and an empty search. Expanded messages show context with the matching
line highlighted, the full source-log path, diagnostic code, rule and reason.
Source-log links point to the original captured log or retained historical copy.
Logs and reports can be moved together while preserving relative links.
If no diagnostics match, the view says that no active log diagnostics were
recognized; it does not claim that the execution or test results are clean.

Assistant support
------------------

``ptk maintainer sync agent`` distributes ``ptk-log-analyzer`` and the
``ptk-expert`` custom agent alongside the other PTK authoring skills. In clients
supporting GitHub custom agents, select **ptk-expert**. It routes requests to the
relevant skill and starts diagnostics from existing reports/logs. It does not
automatically rerun jobs, hide errors or justify findings without evidence.
