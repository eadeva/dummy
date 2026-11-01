---
name: ptk-devops
description: Maintain or review local onboarding, tools and Docker images, external configuration policy, artifact delivery and CX automation in any project using PTK. Use for cross-cutting DevOps or maintainer tasks spanning several PTK features; route detailed implementation to the relevant skill without assuming the consumer is PTK's source repository.
---

# PTK DevOps and project maintenance

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Work from the consumer's installed CLI, root marker, actual configuration directory and permitted invocation routes. Do not require PTK source, a Python package, a particular build system, or jobs named build, verify or package.

## Establish scope and ownership

1. Identify whether the request concerns local development, a container image, native CX automation or a release handoff. Keep local-only requests local. Record actual repositories, variants, producer jobs, tools, runners and existing workflow files before changing them.
2. Inspect `ptk --version`, `ptk describe --json` and only the relevant `--configuration` sections. Read the consumer's onboarding and release conventions. A maintainer task does not grant maintainer access: inspect the applicable role and preserve its configured identity list. Do not use environment overrides or edit maintainers to bypass access checks.
3. Distinguish project-owned configuration and instructions from managed assistant references, external base copies, generated outputs, execution evidence and local caches. Use the smallest coherent change; preserve unrelated local edits. A requested review does not authorize installation, job execution, external transfers or workflow dispatch.

## Select the operational path

| Task | Procedure and detailed skill |
|---|---|
| Fresh checkout, local hooks or missing tool | Read [local setup](../../../docs/guides/local-setup.rst), then [tools setup](../ptk-tools-setup/SKILL.md) or [shared configs](../ptk-shared-configs/SKILL.md). Inspect tool requirements and hook status before requesting installation. |
| Container readiness | Use [tools setup](../ptk-tools-setup/SKILL.md). Verify required versions in the actual container environment. `docker: false` disables installation only; report every unavailable/incompatible tool and correct the image/PATH. PTK does not build or launch a container merely because this field exists. |
| Shared policy update | Use [shared configs](../ptk-shared-configs/SKILL.md). Pin the approved source/revision, preview and synchronize explicit mappings, validate offline, then inspect deviation JSON. Preserve bases and project overlays separately; never edit hashes to hide changes. |
| Jobs and local orchestration | Use [job authoring](../ptk-job-authoring/SKILL.md) and [workflow authoring](../ptk-workflow-authoring/SKILL.md). Declare explicit dependencies, outputs and resource ordering; do not infer artifacts or opt into cache automatically. |
| Callable GitHub CX workflow | Use [GitHub workflows](../ptk-github-workflows/SKILL.md). Generate or review the setup matrix, producer needs, individual job execution and upload/download wiring. Preserve project runner, Docker, event, secret-name and VMR-checkout TODOs until actual choices are supplied. |
| Package/release handoff | Use [package preparation](../ptk-package-preparation/SKILL.md), [versioning](../ptk-versioning/SKILL.md) and [credentials](../ptk-credentials/SKILL.md). Verify artifact identity and exact completed manifests. Preparing artifacts does not imply publishing or tagging. |
| Failed runs or broken setup | Use [troubleshooting](../ptk-troubleshooting/SKILL.md) and [log analysis](../ptk-log-analyzer/SKILL.md). Diagnose recorded evidence first; preserve original process failures and run identity. |

## Review integration boundaries

4. For local setup, enabled hooks are checked before real jobs, not automatically on clone or extension activation. Required tools are checked; `--setup` or an ordered `tools.ensure` step requests installation. External configuration freshness is explicit (`ptk validate --generated`), not an automatic job prerequisite. Keep uv.lock beside its owning pyproject.toml.
5. For CX, select approved Action/PTK versions and real project-owned images, runners and checkout rules. Generated workflows call the variant-matrix command first; each execution job depends on setup and its producers. Do not run local PTK workflows remotely or use last-finishing matrix outputs as producer identity. Generation does not execute or dispatch a workflow.
6. Keep artifact destination identity from setup, actual output paths from completed producers, and downloads relative to the producing repository. Direct files and ZIP folders use the shipped Action contract. `artifact_type` is metadata, not a built-in selective-download filter. Never place credentials in URLs, command arguments, manifests or additional properties.
7. Treat cache as an optional project responsibility: explicit outputs plus `cache: true`, content-based matching, root steps/jobs always run, and `--no-cache-ptk` bypasses PTK reuse. Do not use successful reuse as proof that a remote artifact/service is still available.
8. Use CX in explanations and documentation. Use `PTK_CX`, `--cx`, `--no-cx` and expression `cx` for PTK interfaces. Preserve external provider variables such as `CI` and third-party action names. Mise is not currently a built-in PTK installer; do not invent configuration fields or silently change tool managers.

## Verify and hand off

9. Validate the owning configuration, inspect the affected job/workflow preview after considering version-command effects, and run only the checks authorized by the task. For authored GitHub YAML, distinguish local validation from an actual hosted run. Keep platform acceptance separate from checks run on the current host.
10. When assistant resources are in scope, use `ptk maintainer sync agent --check` and the authorized synchronization. Keep project-specific instructions separately owned; do not patch installed examples or regenerate over custom edits.
11. Report the concrete change, affected owners/paths, checks actually performed, remaining TODOs and the next operational action. Clearly distinguish reviewed, generated, installed, executed, uploaded and published states. Escalate only a specific missing decision or permission; continue independent authorized work.

Use `when` for job and step eligibility; never author `only_cx`, `only_variants`
or `omit_variants`. Job conditions accept only CX and resolved variant context
(`cx`, `variant`, component/feature symbols and `vh`); use `os`, `env`, `params`
and `vars` only on steps. Combine migrated filters with `and`. Check enabled and
disabled variants. False job conditions skip execution and block dependent branches.

Treat every declared output as required. Verify the producer actually creates it;
missing outputs fail before consumers and cannot be tolerated by `continue_on_error`.
Partial runs validate executed step outputs only; detached GUI launchers cannot
promise outputs. Existing files satisfy existence checks, so keep semantic freshness
and cache correctness project-owned. Never publish an `outputs_valid: false` manifest.

For generated workflows, preserve setup's per-invocation `has_jobs_*` outputs and
job guards for empty matrices. Matrix export prunes false rows and dependent rows,
including mapped repository variants. Review existing project-owned workflows
explicitly; generation never overwrites them. Do not claim hosted execution from
local validation alone. Read the linked execution and GitHub workflow docs for details.
