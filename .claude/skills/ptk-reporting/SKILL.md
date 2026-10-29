---
name: ptk-reporting
description: Add ptk report formats, import tool results or troubleshoot report generation.
---

# ptk-reporting

First follow the [project discovery and execution guide](../../../docs/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read the report commands in [docs/cli.rst](../../../docs/cli.rst) and extension contracts in [docs/plugins.rst](../../../docs/plugins.rst).

2. Write tool results to PTK_STEP_REPORTS_DIR or `${run.reports_dir}` for the producing step.

3. Use `report.import` with file globs to copy results from other folders; set optional only when absence is acceptable.

4. Recognized inputs are JUnit XML, Cobertura XML and SARIF; select output formats under report_formats.

5. Use existing recorded files first. For an export request, select the discovered repository/job/variant and `--run RUN_ID` for history; use `ptk report export JOB -f json` and inspect the printed output path. HTML is the default, so JSON need not exist. Exports write files; use a separate output directory when preserving existing evidence. Do not rerun jobs just to change report format.

6. Keep report problems separate from the job exit status and preserve skipped/allowed-failure semantics.

7. Test malformed files, escaping, totals and relative log links when changing exporters/importers.

8. Register external exporters/contributors with `ptk.reporters` / `ptk.report_contributors` and select the installed distribution in `plugins`. Follow [docs/plugins.rst](../../../docs/plugins.rst).

9. `report: false` excludes a step subtree from reports and imports, but does not hide audit logs or change failure status.

10. Never include secrets in imported results; masking engine logs does not sanitize arbitrary third-party files.

Historical input snapshots travel with run summaries. Reproduce with two runs producing different input files; historical export must not import the newer results.


Read [report summaries](../../../docs/configuration.rst) for recorded project/PTK versions, variant details and declared tool sources. Test cards count executed (excluding skipped), passed, skipped and failed (including errors); green/red/gray convey status and text retains the meaning. Per-column filters combine without changing recorded totals. `needs.json` is not a supported importer.

Set a job's `open_report` to `always` or `on_errors` only when automatic local opening is wanted; omission disables it and CX/dry-run suppress it. Errors include failed steps/tests, error findings and report import problems. Browser availability must not alter the run's exit status.

For local orchestration, inspect the workflow summary and immutable child reports under the workflow run directory. Read [workflows](../../../docs/workflows.rst); do not merge test cases from unrelated repositories without preserving their context.

Workflow `open_report` defaults to `always`. Use `on-errors` (hyphen) to include tolerated execution failures and imported report errors, or `null` to disable opening. When the summary is selected for opening, suppress child openings; otherwise apply child policies after completion using retained snapshots. CX/dry-run never open the summary; browser or summary-write failures must not change execution exit codes. Summary links are HTML-only; retain internal run summaries and captured inputs for regeneration. Print report file paths without starting a localhost server; preserve configured automatic opening and explicit `ptk report open`.

Use [log analysis](../../../docs/log-analysis.rst) and [the log-analyzer skill](../ptk-log-analyzer/SKILL.md) for captured warnings/errors, disposition rules and source-log evidence. Keep severity and disposition separate; never change job exit codes to match suppressed findings.
