---
name: ptk-reporting
description: Add ptk report formats, import tool results or troubleshoot report generation.
---

# ptk-reporting

1. Read `src/ptk/domain/reporting/model.py`, `src/ptk/adapters/reporting/` and the ReportStore port.

2. Write tool results to PTK_STEP_REPORTS_DIR or `${run.reports_dir}` for the producing step.

3. Use `report.import` with file globs to copy results from other folders; set optional only when absence is acceptable.

4. Recognized inputs are JUnit XML, Cobertura XML and SARIF; select output formats under reporting.formats.

5. Inspect `report.json`, then regenerate with `ptk report export ACTION -f html` or open with `ptk report open ACTION`.

6. Keep report problems separate from the action exit status and preserve skipped/allowed-failure semantics.

7. Test malformed files, escaping, totals and relative log links when changing exporters/importers.

8. Register external exporters/contributors with `ptk.reporters` / `ptk.report_contributors` and select the installed distribution in `plugins`. Follow `docs/plugins.rst`.

9. `report: false` excludes a step subtree from reports and imports, but does not hide audit logs or change failure status.

10. Never include secrets in imported results; masking engine logs does not sanitize arbitrary third-party files.

Historical input snapshots travel with run summaries. Reproduce with two runs producing different input files; historical export must not import the newer results.
