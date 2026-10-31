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
change the process exit result. Active errors can trigger ``open_report:
on_errors`` under the existing report policy.

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
