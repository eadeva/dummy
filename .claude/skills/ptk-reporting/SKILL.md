---
name: ptk-reporting
description: Add ptk report formats, import tool results or troubleshoot report generation.
---

# ptk-reporting

1. Read the report commands in [docs/cli.rst](../../../docs/cli.rst) and extension contracts in [docs/plugins.rst](../../../docs/plugins.rst).

2. Write tool results to PTK_STEP_REPORTS_DIR or `${run.reports_dir}` for the producing step.

3. Use `report.import` with file globs to copy results from other folders; set optional only when absence is acceptable.

4. Recognized inputs are JUnit XML, Cobertura XML and SARIF; select output formats under reporting.formats.

5. Inspect `report.json`, then regenerate with `ptk report export JOB -f html` or open with `ptk report open JOB`.

6. Keep report problems separate from the job exit status and preserve skipped/allowed-failure semantics.

7. Test malformed files, escaping, totals and relative log links when changing exporters/importers.

8. Register external exporters/contributors with `ptk.reporters` / `ptk.report_contributors` and select the installed distribution in `plugins`. Follow [docs/plugins.rst](../../../docs/plugins.rst).

9. `report: false` excludes a step subtree from reports and imports, but does not hide audit logs or change failure status.

10. Never include secrets in imported results; masking engine logs does not sanitize arbitrary third-party files.

Historical input snapshots travel with run summaries. Reproduce with two runs producing different input files; historical export must not import the newer results.


Read [report summaries](../../../docs/configuration.rst) for recorded project/PTK versions, variant details and declared tool sources. Test cards count executed (excluding skipped), passed, skipped and failed (including errors); green/red/gray convey status and text retains the meaning. Per-column filters combine without changing recorded totals. `needs.json` is not a supported importer.

Set a job's `open_report` to `always` or `on_errors` only when automatic local opening is wanted; omission disables it and CX/dry-run suppress it. Errors include failed steps/tests, error findings and report import problems. Browser availability must not alter the run's exit status.

For local orchestration, inspect the workflow summary and immutable child reports under the workflow run directory. Read [workflows](../../../docs/workflows.rst); do not merge test cases from unrelated repositories without preserving their context.

Workflow `open_report` defaults to `always`. Use `on-errors` (hyphen) to include tolerated execution failures and imported report errors, or `null` to disable opening. When the summary is selected for opening, suppress child openings; otherwise apply child policies after completion using retained snapshots. CX/dry-run never open the summary; browser or summary-write failures must not change execution exit codes. Summary links are HTML-only; retain JSON artifacts. Print report file paths without starting a localhost server; preserve configured automatic opening and explicit `ptk report open`.
