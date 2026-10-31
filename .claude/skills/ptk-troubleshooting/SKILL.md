---
name: ptk-troubleshooting
description: Diagnose PTK discovery, configuration, permission, startup, environment, tool and execution failures. Use for invalid or missing projects, commands that fail before a job starts, or differences between machines and PTK versions.
---

# PTK troubleshooting

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Reuse existing evidence before reproducing a failure.

1. Record the selected PTK version/launcher, working directory, repository, variant, non-secret parameters and observed error. Separate configuration failure, denied access, preparation failure, step failure and report-generation problems.
2. For loading errors, inspect `ptk validate` and the reported source file/line; use `ptk describe --json --configuration` when available to recover document ownership and diagnostics. Do not initialize over an invalid project or rename an authored field to match a different release.
3. For denied operations, inspect the applicable identity and maintainer list without changing them. Workspace and member permissions are independent. Do not use environment overrides or edits to grant yourself access.
4. For execution failures, use [log analysis](../ptk-log-analyzer/SKILL.md). Locate outputs from layout/recorded paths, not a fixed `_logs` directory. A valid project or installed PTK is not required to inspect supplied logs. JSON exports are optional; preserve the original run's identity and inputs.
5. For environment failures, inspect the actual interpreter, selected tools, isolated PATH, platform shell syntax and quoting. Use [Python steps](../ptk-python-steps/SKILL.md) or [tools setup](../ptk-tools-setup/SKILL.md). Inspect checks before running `ptk self-service doctor`; diagnostics can execute configured commands.
6. For unexpected variant conditions, inspect `ptk variant show NAME` and `ptk variant explain NAME FEATURE`. For credentials, start with `ptk self-service creds list NAME`; never fetch values merely for diagnosis.
7. Preview only the relevant execution path after checking preparation effects. Reproduce a real run only within the user's scope; deploying, publishing, deleting or exercising credential-test commands is not implied by a request to explain an error.
8. Distinguish usage/configuration errors (2), failed job (1), success (0) and cancellation (130). Retain exact evidence for the original failure. Suggest the smallest corrective change and verify it with focused checks; a changed error message alone is not proof of success.

For missing downloads or stale/reused outputs, inspect declared outputs, producer selectors and the exact completed upload manifest. Compare run scope, repository/job/variant/version/commit and setup-resolved URL before changing storage rules. Use [GitHub workflows](../ptk-github-workflows/SKILL.md) for native pipelines and [output reuse](../../../docs/guides/output-reuse.rst) for local cache decisions; timestamps alone do not identify cache changes.

For slow startup/help, use [performance profiling](../../../docs/guides/performance.rst). Separate launcher/environment synchronization from PTK startup. Compare equivalent targets in the same environment; keep profiles local. Do not add stale caches, disable validation or assume the consumer contains PTK's profiling scripts.
