---
name: ptk-workflow-authoring
description: Create, inspect or troubleshoot local PTK workflow documents, including sequential and parallel job groups, cross-repository VMR calls, failure handling, reports and VS Code tasks. Use for combining existing jobs into a local pipeline; GitHub template generation is not implemented yet.
---

# PTK local workflow authoring

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [workflows](../../../docs/guides/workflows.rst) and the target repositories' `.main.ptk.yml` files. Locate `repository.config_path`; use `ptk repos` from a VMR root to verify aliases. Read existing job definitions before composing them. Workflows run locally, not on CX; do not generate or claim support for GitHub templates.
2. Put each workflow body in `workflows/<name>.ptk.yml` under the owner's configuration folder. For workspace workflows use `workflows/<name>.ptk.yml` at the VMR root and specify `repo` on every leaf. Keep repository-owned names separate; do not merge equal names from different repositories.
3. Build an ordered list of named `steps`. Use `{job: JOB}` for a local job or `{repo: ALIAS, job: JOB, variant: VARIANT, params: {PARAM: VALUE}}` for a VMR job, substituting discovered identifiers and typed values. Confirm each parameter and variant exists in that target. Omit variant to use its repository's normal selection. Never place secret values in workflow params.
4. Use a group with `parallel: true` and nested `steps` for independent jobs. Default to sequence for shared outputs, hardware or services. Parallel branches cannot call the same repository/job/variant or share a `python.project` environment. `max_workers` bounds active job calls across groups. Keep tool paths, credentials and environment configuration in each job's repository.
5. Retain the default stop-on-failure behavior unless continuation is intended. `continue_on_error` tolerates the selected call/group but leaves its failure visible in reports. Cancellation is never tolerated. Put step retries, timeouts and cleanup in the job, not in invented workflow fields.
6. Run `ptk validate`; use the discovered workflow help/execution route for inspection and `--dry-run`. Maintainer workflows need the maintainer prefix. At a VMR root select member workflows as `ALIAS/NAME`; under `ptk ALIAS workflow`, use `NAME`. Preflight validates every call; resolve missing prerequisites in the target repository before execution. Use a job's `--dry-run` for command-level details.
7. Run `ptk workflow run NAME` when executing the requested jobs is authorized. Check exit status, workflow summary and child reports. Workflow `open_report` defaults to `always`; use `on-errors` for failures (including tolerated failures and imported report errors) or `null` to disable opening. CX and dry runs never open it. Child jobs keep their own policies. Read [reporting configuration](../../../docs/guides/configuration.rst) when imported results or job report opening need adjustment.
8. Workflow names are also direct commands (`ptk NAME`), listed in help. Local job/workflow collisions prompt; CX chooses the job. Scripts must use the explicit `run` or `workflow run` form. A workflow summary selected for opening suppresses child openings; otherwise child policies apply after completion.
9. When generated tasks are in scope, run `ptk maintainer sync tasks` and its `--check` mode. For a VMR, generate root workflow tasks and member job/workflow tasks where needed. Preserve user tasks. Use [the complete example](../../../examples/workflows/app/config/workflows/verify.ptk.yml) and [its repository workflow](../../../examples/workflows/app/config/workflows/all.ptk.yml) as tested syntax, not as assumed repository names or jobs. See [editor integration](../../../docs/guides/editor.rst) for interactive terminal browser links and the external-browser setting.

A workspace-owned `audience: maintainer` workflow uses `maintainers.ptk.yml` at
the VMR root. Member jobs retain their own role checks. Lists contain login IDs;
`PTK_ROLE=maintainer` does not grant access. Editor task generation is maintainer-only;
use `--users-only` for shared tasks. See [configuration](../../../docs/guides/configuration.rst).
