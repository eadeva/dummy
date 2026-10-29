---
name: ptk-troubleshooting
description: Diagnose a failing ptk command, configuration, variant, tool or execution
  step.
---

# ptk-troubleshooting

1. Reproduce with the same config, variant and explicit parameters; record versions and the exact non-secret command.

2. Run `ptk validate` first; use `ptk maintainer config show --sources` for layering mistakes.

3. Use `ptk -V VARIANT JOB --dry-run` to inspect commands, conditions and parameter sources.

4. Use `ptk variant explain NAME FEATURE` for unexpected conditions and `ptk self-service doctor` for machine/tool problems.

5. Use `ptk self-service creds list NAME` to inspect provider availability without printing values.

6. Read `_logs/VARIANT/JOB/run.log`, step logs and events.jsonl; correlate with report.json.

7. Distinguish usage/configuration errors (2), failed job (1), success (0) and cancellation (130).

8. Reduce the issue to a disposable configuration and add a regression test before changing core behavior.

9. Check platform shell syntax, PATH case handling, quoting and Python runtime selection before changing a command.

10. Avoid rerunning deployment or credential test jobs until their effects are understood.

For slow startup/help, follow [performance profiling](../../../docs/performance.rst).
Compare root and repository-qualified help, record repository/config sizes and
plugins, and profile using the Python environment containing PTK. Separate
installer/uv synchronization from PTK startup. Keep profiles local and preserve
maintainer filtering; do not suggest stale disk caches or skipping validation.
