Reading execution reports
=========================

Job and workflow reports use the same offline HTML layout. Start with the run
identity and overview, inspect **What failed**, then open execution details or
the underlying evidence. The sticky navigation links to each section. Links
from summaries reveal their target even when a filter or collapsed parent
would otherwise hide it.

Overview and ownership
----------------------

Headers identify the owner, variant, recorded run and elapsed duration. Job
reports also show the project and recorded version. Workflow execution entries
identify the invocation, repository, job and actual variant; their configuration
section contains each child's recorded project/PTK version, variant features,
tool dependencies and parameters. A workspace workflow has workspace scope,
not an invented common product variant.

Workflow identity is purple, job identity cyan and step identity blue. Outcomes
have independent text labels and colors: passed green, failed red, skipped gray
and cancelled amber. Allowed failures keep their failed outcome and an explicit
annotation. Zero counts are neutral. Light/dark themes and narrow layouts use
the same content.

Overview counts link to execution, tests and diagnostics. These are distinct
measurements: a failed process, a failed test and a matching log message can be
three records of related evidence. They are not three failed tests. A successful
process can still have imported test failures or active error diagnostics. PTK
does not rewrite execution outcomes based on report filters or findings.

Execution, graphs and timelines
--------------------------------

Select an execution row to inspect the command, prerequisites, attempts, exit
code, captured log and reason when recorded. Workflow rows also expose their
steps and links to immutable child HTML/JSON reports. **Show in graph** selects
the corresponding graph node. Graph selection opens the matching execution
record; **Open execution details** scrolls to it. Timeline rows use the same
navigation.

The dependency graph starts collapsed. In a workflow graph, every job with
recorded step topology has a **Show steps** control. Expanding it shows its
internal step graph inside a job container; **Expand all jobs** and **Collapse
all jobs** operate on all containers. Controls support keyboard activation as
well as pointer input. Zoom, pan and fit remain available.

Job-to-job edges always connect whole jobs. Internal edges connect steps only.
Expansion does not invent dependencies between arbitrary steps of different
jobs, or change the scheduler's readiness rules. Shared steps appear once with
all prerequisite edges. Step identities are scoped by invocation, so equal step
names in different jobs remain distinct. Expansion relays out the graph and fits
it to the viewport; zoom in for detailed inspection of a large graph.

Graphs use saved topology and outcomes, never today's YAML. A job blocked before
execution retains its prepared step topology with **Not run** states and the
job's blocking reason. Those states are not fabricated skipped executions. A
step with ``report: false`` exposes only its name, edges and **Details hidden**
marker, including inside an expanded workflow job.

The graph describes dependencies. The timeline describes recorded start offsets
and elapsed duration, so overlapping bars show concurrency. Skipped/not-run
records have no execution duration. Job-level workflow durations can include
report collection; they are not the sum of the child step durations.

Failures and diagnostics
------------------------

**What failed** lists active errors with owner, source, concise reason and a link
to detailed evidence. It retains allowed execution failures. Detailed diagnostics
share one expandable presentation for execution, imported tests, static analysis,
log analysis and report-collection problems. Filter by source, severity,
disposition, owner and step, and combine these with text search. Source labels
remain visible; presenting evidence together does not infer that matching-looking
messages have the same cause.

Log occurrence cards apply source/severity/disposition filters. Ignored and
justified findings are initially hidden; their reasons and original severity
remain available. Reset restores active findings across all sources. Searching
a log diagnostic matches its message, owner, file, tool, rule and disposition
reason, rather than unrelated neighboring lines in its context excerpt. Selecting
a failure link clears conflicting filters only when needed to reveal its target.

Tests have their own result filter and search, with per-test detail and imported
suite/source identity. Test totals exclude log occurrences and execution records.
Unreadable evidence is a report-collection diagnostic, not a successful check.
See :doc:`log-analysis` for recognition, bounds and disposition rules.

Evidence, portability and responsibility
----------------------------------------

The evidence section links to captured logs and recorded child reports, with
imported coverage when present. Workflow children link back to the aggregate
report. Links use relative paths where possible; move a report together with
its referenced evidence. The HTML embeds styles, behavior, graph data and its
layout engine. It needs no network, report server or current project checkout
to display the saved information. Links to external evidence still require the
referenced files. Unavailable child evidence is reported without inventing results
or changing execution exit codes.

The workflow JSON snapshot contains its context, child report data and nested
graph. Child snapshots preserve report-disabled steps and secret masking, and
later job executions cannot change their embedded results. HTML is the human
view, JSON is structured data, JUnit is test/CI interchange and Markdown is the
compact CI summary. Workflow reports currently export HTML/JSON; job reports
support the complete format set.

Project implementations own artifact correctness, output validation, side
effects, retry safety and isolation. PTK deliberately leaves projects free to
choose their tools and checks; a green execution badge records execution success,
not independent verification of produced artifacts. Historical comparisons,
trends and flaky-test analysis are outside this report redesign.

See :need:`DD_REPORT_EXPLORATION`, :need:`REQ_Sw_REPORT_EXPLORATION` and
:need:`REQ_Sw_REPORT_GRAPHS`.

Sphinx documentation and needs
------------------------------

PTK imports documentation evidence produced by **Sphinx 9.1.0** and
**Sphinx-Needs 8.5.0**. No Sphinx package is required in PTK's own environment:
the project runs its chosen documentation tools, and PTK reads their JSON output.
Enable the needs export in the project's ``conf.py``::

   needs_build_json = True

For example, a documentation step can write HTML into its build directory:

.. code-block:: yaml

   steps:
     sphinx:
       run:
       - python
       - -m
       - sphinx
       - -W
       - --keep-going
       - -b
       - html
       - docs
       - ${run.build_dir}/html

After execution, PTK discovers ``needs.json`` and ``schema_violations.json``
recursively inside each executed, report-visible step's **build directory**.
It does not look for these exports in ``run.log_dir``. Configured layout roots
are respected. Symbolic-link directories are not traversed and artifacts must
remain inside the step build directory. Each JSON file has a fixed limit of
**100 MiB (104,857,600 bytes)**, applied separately to ``needs.json`` and
``schema_violations.json``. Files exactly at the limit pass the size check;
larger files are excluded with a report-collection diagnostic, without changing
the job's execution result. Unreadable or malformed exports also produce
report-collection diagnostics. The limit accommodates larger needs catalogs
while retaining a finite input-size guard. It is not a process-memory budget:
parsed objects, retained data and rendered reports can require more memory.
Skipped, blocked, never-started and ``report: false`` steps are not imported.

The selected ``current_version`` is imported, including an empty version string
when used by the project. Historical versions embedded in the same file do not
inflate the counts. When ``needs_defaults_removed`` is enabled, exported schema
defaults are restored. Custom fields and nested validation details are retained.
Separate output directories, jobs and variants remain separate evidence sources,
even when their need IDs are identical. Need parts remain in their parent's
recorded fields; they are not counted as independent top-level needs.

The **Sphinx documentation** section contains:

* A type-distribution donut and lifecycle-status bars, with exact counts and
  accessible text legends. Selecting a legend filters the table. Charts always
  describe all imported records; project-defined statuses are not interpreted
  as implementation progress or execution outcomes.
* A searchable table of IDs, titles, types, statuses, tags, validation findings,
  owners and sources. Expand a title to inspect the captured fields. Combine
  filters for type, status, owner, step, source and validation severity.
* Source/version metadata, captured JSON links and the number of needs validated
  when reported by Sphinx-Needs. An absent violations file means **validation not
  reported**, rather than zero violations.

Schema severity ``violation`` maps to a PTK error, ``warning`` to a warning and
``info`` to a note. The schema severity takes precedence over the console logging
level. These findings use the **Sphinx-Needs** source in the shared Diagnostics
view; errors also appear in **What failed**. Nested validation reasons belong to
their parent finding and are not counted again. Suppressed console messages can
still be present in the JSON export. Related log findings retain their separate
source; PTK does not infer that matching-looking records have the same cause.
Neither needs nor violations are additional tests, and importing them does not
change the process exit result. Active errors automatically open the dedicated diagnostics report locally.

When the producing step **passed** and an HTML ``index.html`` exists, the report
offers **Open docs**. PTK checks the export directory, its ``html`` subdirectory,
and a sibling ``html`` directory for a separate ``needs`` builder output. Need
IDs link to their local HTML document/anchor when that document exists. Failed
or cancelled builds can still contribute diagnostic evidence but do not advertise
a successful documentation build. Other Sphinx builders and external need URLs
are not guessed.

The JSON exports and normalized data are captured with the run's report inputs.
Retained runs and workflow child snapshots therefore preserve their needs and
violations after rebuilds or configuration edits. HTML is self-contained for
charts, tables and diagnostics; JSON includes the structured needs and counts;
Markdown/GitHub summaries include distributions, findings and documentation links.
JUnit keeps its existing execution/test meaning. These are additions to the
existing exporters, not a new Sphinx builder or plugin interface.

The built HTML documentation site is **linked, not copied**. Its files must
remain available, and a later build can replace what that link opens. Projects
own output freshness and cleanup: PTK captures the files left by an executed
step, without proving that every artifact was regenerated or validating the
project's requirements itself. A successful build is not proof of requirement
completeness, traceability or implementation correctness.

See :need:`DD_SPHINX_EVIDENCE` and :need:`REQ_Sw_SPHINX_REPORTS`.

CMake configuration evidence
----------------------------

PTK selects one of two shipped importers automatically, using the CMake
executable in the actual command environment, including its step-specific PATH.
It runs that executable's ``--version`` before a direct configure command and
records the version and executable with the evidence. Exporting historical
reports never probes the current machine. Unsupported versions below 3.2 and
unreadable evidence produce collection diagnostics without changing exit codes.

.. list-table:: Importer selection and available information
   :header-rows: 1
   :widths: 22 22 56

   * - Detected version
     - Importer
     - Evidence
   * - 3.2 through 4.0.x
     - ``cmake-3.2``
     - CMake console errors/warnings and selected cache metadata. Before 3.26,
       retain changed CMakeOutput.log/CMakeError.log probe output as unclassified
       information. From 3.20, request targets and toolchains through the File API;
       from 3.26, import structured configure checks; from 4.0, also capture SARIF.
   * - 4.1 and newer
     - ``cmake-4.1``
     - SARIF errors/warnings, current File API targets/toolchains, versioned
       configure events, package/file discovery, requested/discovered versions,
       search candidates and source call stacks. Failed configure runs can use
       the File API error reply without reusing a previous successful target model.

For automatic preparation, use a direct CMake executable in a list command or
a simple shell command without shell expansion/operators. An explicit build
directory is recommended::

   configure:
     run: [cmake, -S, ., -B, "${run.build_dir}"]

The actual ``-B`` directory is used; PTK does not change cwd or overwrite the
project's build directory selection. Older positional source/existing-build
invocations are supported. A configure preset needs an explicit ``-B`` for
automatic instrumentation. PTK creates its own File API client queries, preserving
other clients, and captures SARIF where supported. It respects an explicit
``--sarif-output`` path. It does not enable suppressed CMake warnings or change
warning-as-error settings. Only diagnostics actually emitted by CMake are imported.

Scripts, wrappers, compound shell commands and presets without ``-B`` are not
rewritten. Their changed caches beneath ``run.build_dir`` can identify the CMake
version that wrote them, and already-produced evidence can be imported. They
must prepare structured outputs themselves for complete reporting. Unchanged
caches are not assigned to unrelated commands. CMake build/install/script/tool
modes are not instrumented as configure commands. Compiler/linker diagnostics
remain the responsibility of their own report formats and PTK log analysis.

The HTML CMake section shows configuration metadata, toolchains, searchable
checks/packages/targets and collapsed target dependency graphs. Targets are
configured targets, not claims of successful compilation. Negative compiler
feature probes and absent optional packages are informational, not errors or
JUnit tests. CMake errors and warnings appear in shared Diagnostics; developer
and deprecation warnings retain their categories. Profiling is not collected.

Only new configure events and current File API replies are used. Each attempt,
including retries, retains its own normalized snapshot with the run's report
inputs; later build changes cannot alter it. CMake artifacts and captured console
text have a 100 MiB input limit each; this is not an aggregate or memory budget.
Malformed/oversized inputs are reported, with other available evidence retained.
Unknown event versions are ignored as required by CMake's versioned protocol.
Missing evidence is labelled unavailable rather than successful. Imported text
is masked before persistence, and HTML escapes project-supplied content.

Matching CMake findings from SARIF and console output are merged, then matched
against PTK log analysis using owner/step, severity, source location and normalized
message. Their details list contributing sources. Ambiguous matches remain
separate with explicit source labels. The existing ordered ``log_analysis.rules``
apply to these findings; ignored/justified warnings and errors remain available
with their original severity, rule and reason. Rules are taken from the saved
run, not from current configuration. See :need:`DD_CMAKE_REPORTS` and
:need:`REQ_Sw_CMAKE_REPORTS`.

Bazel build and test evidence
-----------------------------

PTK imports Bazel's newline-delimited JSON Build Event Protocol (BEP) with one
shipped ``bazel-bep-json`` importer. The producing stream records the actual
``buildToolVersion`` and invocation UUID, including the version selected by
Bazelisk. Report regeneration never probes the current PATH. BEP uses optional
fields across Bazel releases; PTK consumes the documented event contract,
ignores unknown event kinds and displays missing evidence as unavailable. It
does not invent major-version parser boundaries or fall back to an older report.

Direct ``bazel`` and ``bazelisk`` commands for ``build``, ``test``, ``coverage``
and ``run`` automatically receive a temporary ``--build_event_json_file`` path.
Startup options, working directory, environment, target arguments and the
arguments after ``bazel run ... --`` retain their meaning. An explicit JSON
output path on the command line is reused; an explicitly empty path disables
structured capture. When PTK supplies the path it takes precedence over a JSON
output destination from ``.bazelrc``; pass that destination explicitly to retain
it. PTK does not edit ``.bazelrc`` or alter output bases, caches, execution
strategies, warning settings or test retries. Other Bazel commands are not
instrumented. A separate version probe is unnecessary and does not start another
server or trigger another Bazelisk download.

For example::

   steps:
     test:
       run: [bazel, test, //...]

List commands and simple quoted shell commands are supported. Compound shell
commands, scripts, ambiguous startup options and unknown wrappers are not
rewritten. They can write a
``*.bep.json`` or ``*.bep.jsonl`` below ``${run.build_dir}`` or the producing
step's reports directory. Only changed files are captured for an executed step;
unchanged build-tree files are not assigned to another invocation. Alternatively,
use ``report.import`` to copy a BEP file with either suffix directly into the
step's reports folder. Each file must contain one invocation, one JSON event per
line; binary/text-protobuf BEP files and JSON arrays are not accepted. Console
output from a wrapper is not assigned to an arbitrary stream; BEP progress
events carry that invocation's output, and ordinary PTK log analysis remains
available.

The full HTML report adds a Bazel section containing:

* Producing version, invocation UUID, workspace, command result, Bazel's build
  exit result and stream completeness. For ``bazel run``, a successful build
  does not imply the launched program succeeded; PTK preserves the process result.
* Searchable target/configuration/aspect results, reported actions, test-target
  summaries, attempts, shards, runs and local/remote test-cache indicators.
* Build metrics with exact recorded counters. ``actionsExecuted`` includes remote
  cache hits and excludes local action-cache hits; it is not a cache-hit ratio.
  Bazel normally emits action events for failures, so their count is not the
  total number of executed actions. Missing optional metrics are not zero.
* Artifact references, with links to available local files. Remote/bytestream
  URIs are displayed without fetching them. Artifact contents, profiles and
  binary blobs are not imported. Local links can expire after a later build.

Test-target outcomes are separate from individual JUnit cases. Failed attempts
followed by a successful retry do not become permanent test errors: the final
``FLAKY`` target summary is a warning and the individual attempts remain visible.
An imported JUnit case failure and its Bazel test-target summary have different
granularity and retain their source labels. BEP targets/attempts do not increase
JUnit totals. BEP event relationships are not a target dependency graph.

The full report includes a collapsed **Build target dependencies** graph, using
Bazel's built-in ``cquery``. It shows libraries, binaries, tests and other rule
targets with shared dependencies appearing once. Source/output files, toolchains
and configuration helper rules are omitted; generated-file dependencies connect
to their producing rule. External libraries appear as boundary nodes without
expanding their internals. Select a node for its dependencies, configuration and
recorded status; zoom, pan and fit work offline. Only target results actually
recorded by BEP get passed/failed states. Other targets remain ``configured``.

After a supported direct invocation, PTK runs a bounded ``cquery`` using the same
launcher, environment, working directory and startup arguments. It replays the
canonical expanded build options, including ``.bazelrc``/``--config`` settings,
without rereading rc files or forwarding program arguments. Reporting destinations
are removed so the query does not overwrite the original BEP/profile or publish
another BES stream. This is additional analysis, with a separate 60-second timeout;
it does not rebuild targets and does not consume the command's timeout. Step wall
time includes collection. Query failure never changes the original build exit or
duplicates its diagnostics. Configuration checksums must match the recorded build.

Automatic capture requires Bazel 6+ with canonical command options and native
``cquery --output=jsonproto --output_file`` support. If unavailable, cancelled,
too large (over 2,000 displayed targets), or inconsistent with the build, the
report explains why it has no graph. Incomplete/analysis-failed builds may have
no usable graph. A saved report never runs Bazel again. The masked graph snapshot
is retained with each invocation in full job/workflow reports and JSON exports.

For a manual ``report.import``, copy matching ``name.bep.json`` (or
``name.bep.jsonl``) and ``name.cquery.json`` files into the same step report
directory. Produce the latter with the same build options and top-level targets::

   bazel cquery 'kind("rule|generated file", deps(//app:app))' \
     --universe_scope=//app:app --noimplicit_deps --notool_deps --noinclude_aspects \
     --output=jsonproto --transitions=lite --proto:include_configurations \
     --proto:output_rule_attrs= > name.cquery.json

Use the same source revision as the BEP build; matching configurations cannot
detect intervening source edits. PTK validates target/configuration identity and
does not infer graph edges from BEP event links or unresolved ``select()`` inputs.

Bazel warnings, errors and test warnings share the existing Diagnostics section
and ``diagnostics.html``. Matching structured, BEP-progress, console and PTK-log
findings are merged conservatively by step, severity, source location and message,
with contributing sources and occurrence counts retained. Ambiguous matches keep
separate source labels. Saved first-match ignore/justify rules and reasons apply
even when console log analysis is disabled. Dispositions do not change actual
process or test-target outcomes. Local active errors open diagnostics; CX never
opens a browser.

PTK retains masked normalized evidence per execution attempt. Later builds and
workflow snapshots cannot rewrite earlier evidence; temporary raw BEP files are
removed after capture. Explicit project-owned files are left intact. Inputs and
each normalized snapshot are bounded to 100 MiB (104,857,600 bytes); exactly the
boundary is accepted. This is a per-file/console limit, not an aggregate memory
budget. Malformed, conflicting, truncated or incomplete event streams produce
collection diagnostics while retaining readable evidence and preserving command
exit codes. A startup failure may have no BEP/version; captured console errors
remain useful and the missing evidence is explicit. The same step visibility,
retry and history rules apply as for other importers.

See :need:`DD_BAZEL_REPORTS`, :need:`REQ_Sw_BAZEL_REPORTS`, the
`Bazel BEP documentation <https://bazel.build/remote/bep>`_ and its
`event glossary <https://bazel.build/remote/bep-glossary>`_. No Bazel runtime,
protobuf package, Build Event Service or additional plugin is required to read
saved evidence. Target graph capture uses the project's existing Bazel; see
`configured query <https://bazel.build/query/cquery>`_.

GN generation reports
---------------------

GN generates Ninja build files; it does not compile the targets. PTK uses GN's
built-in JSON project export for target information and dependencies. It does not
parse BUILD.gn files, reconstruct Ninja graphs, run Ninja, or launch a second
generation to collect reporting data.

For a direct ``gn gen`` list command or simple shell command, PTK resolves the
executable using the step's PATH and records its ``--version`` output. GN uses
revision identifiers, so JSON support is checked with ``gn help gen`` rather
than a semantic-version boundary. These probes have separate 10-second timeouts
outside the command's timeout. Unsupported GN builds retain console diagnostics
and explicit missing-graph information. For example::

   steps:
     generate:
       run: [gn, gen, "${run.build_dir}"]

When no IDE or JSON-script/output options are already configured, PTK adds
``--ide=json --json-file-name=.ptk.gn-project.json``. This stable build-directory
file is intentional: GN saves those options in Ninja's regeneration rule. Later
regeneration can refresh it without referencing an old report directory or a
deleted temporary file. It remains native, unmasked build output; PTK retains a
separate masked snapshot in the report directory.

Existing IDE choices, JSON destinations, scripts, filters and other arguments
are preserved. A different IDE or dormant JSON script/output option prevents
automatic instrumentation; select ``--ide=json`` explicitly to supply target
evidence. PTK never enables a dormant JSON post-processing script. Successful
direct JSON generations may retain identical bytes because GN only rewrites
changed exports. Failed/cancelled generations never reuse the old target model.
Reporting parse failures preserve the actual process outcome.

Full job/workflow reports show the generation result, executable and version,
source/build directories, default toolchain and searchable configured targets.
The collapsed offline graph supports zoom, pan and node details. It shows target
types, shared dependencies and toolchain identity; source files and toolchain
commands are omitted. GN's exported dependencies combine linked and data
dependencies. Target states remain ``configured``; generation success does not
establish compilation or test success. Filtered-out dependencies become explicit
unavailable boundary nodes. Above 2,000 graph nodes, target records remain
available and the report explains why it omitted the interactive graph.

Errors and warnings include source locations, bounded multiline explanations and
context. Saved first-match ignore/justify rules apply even when generic log
analysis is disabled. Matching GN and PTK-log findings merge with source labels;
ambiguous matches remain separate. Full and dedicated diagnostics share local
active-error opening and CX browser exclusion. GN does not inflate JUnit totals.

Wrappers can emit changed ``*.gn-project.json`` files below ``run.build_dir`` or
the step report directory. For offline ``report.import``, copy ``project.json`` or
``name.gn-project.json`` to the step report directory. A corresponding
``name.gn.log`` supplies diagnostics; standalone ``*.gn.log`` files are accepted.
Native project JSON does not record the producing GN version or process result,
so these remain unknown for offline/wrapper inputs. Regenerating a saved report
never probes the current PATH or invokes GN.

Inputs, console capture and each normalized snapshot are bounded to 100 MiB
(104,857,600 bytes), with the boundary accepted. Unknown JSON fields are ignored;
malformed/cyclic evidence and unsafe input paths produce collection diagnostics.
Snapshots are immutable per attempt and reused by saved workflow reports. See
:need:`DD_GN_REPORTS`, :need:`REQ_Sw_GN_REPORTS` and the
`GN reference <https://gn.googlesource.com/gn/+/main/docs/reference.md>`_.

Dedicated diagnostics reports
-----------------------------

Every job report export also writes ``diagnostics.html``, including exports with
an empty full-format list. Workflows write one aggregate diagnostics report and
retain each child's dedicated report. These use the same diagnostics and filters
as the full reports: execution, JUnit failures/errors, SARIF, log analysis,
Sphinx-Needs, CMake, Bazel, GN and collection problems. Cobertura contributes coverage to
the full report, not invented diagnostics; malformed coverage is a collection
problem. Warnings remain visible. Active error/warning counts and ignored/justified
counts describe diagnostic records, not numbers of tests.

Local active errors always open the dedicated report, independent of the full
report's ``open_report`` preference. The workflow aggregate takes precedence
over child tabs. Warning-only and suppressed-only findings do not trigger
opening. Actual process failures, including allowed failures, still do.
CX and dry runs never open a browser; CX still writes the report. The full report
continues to follow configured export formats and is linked when generated.
Failure to write a new report never opens a stale one.

The existing first-match ignore/justify rules apply to all imported error/warning
findings, using their producing step, severity and message. For JUnit, match the
failure/error message (or case name if empty). For Sphinx, match the violation
message. Original test results, coverage, process outcomes and raw logs are never
rewritten. Suppression changes diagnostic disposition, active-error handling and
presentation only; execution failures and collection errors are not suppressible
through imported-diagnostic rules. See :need:`DD_DEDICATED_DIAGNOSTICS` and
:need:`REQ_Sw_DEDICATED_DIAGNOSTICS`.

Reused outputs
--------------

Optional PTK caching labels reused steps and workflow jobs **Reused**, records
the original run ID and distinguishes them from newly executed work. Reused
steps have zero attempts, no new exit code or command log, and no execution
duration. JSON retains successful dependency status with ``reused_from``;
JUnit marks these steps skipped. Previously imported tests and diagnostics are
not presented as newly executed evidence. Consult the originating run, subject
to ordinary log retention. See :doc:`output-reuse`.
