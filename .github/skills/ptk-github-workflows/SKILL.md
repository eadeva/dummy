---
name: ptk-github-workflows
description: Create, review or update callable GitHub Actions workflows for a project using PTk. Use for ptk maintainer gen-workflows, cx.ptk.yml (technical user, runner, image, PMT actions, VMR checkout), variant-matrix setup, producer needs, and declared-output upload/download integration. For local PTk orchestration use ptk-workflow-authoring first.
---

# PTk GitHub workflow authoring

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Use the project's installed PTk and configured jobs, variants, paths and permissions; do not assume the consumer contains PTk's source checkout or its example `verify` job.

## Establish the graph and artifact contract

1. Read [GitHub Actions](../../../docs/guides/github-actions.rst) for supported commands, action inputs and limitations, and [matrix setup](../../../docs/guides/cx-matrix.rst) for identity and destination fields. Confirm `ptk maintainer gen-workflows --help` and `ptk maintainer matrix --help` exist in the selected release. If unavailable, explain the version mismatch; do not invent commands or silently upgrade PTk.
2. Find the owning `workflows/NAME.ptk.yml` and all called jobs. If no PTk workflow exists, use [local workflow authoring](../ptk-workflow-authoring/SKILL.md) to create it first. Preserve dependency intent, job keys (`JOB` or `REPO:JOB`), typed parameters and owner `repo_variants` mappings. Each target repository/job can appear only once in a PTk workflow. PTk generates readable GitHub IDs (`job_<job>` or `repo_<alias>_job_<job>`) and rejects collisions naming both targets; resolve those by renaming a repository alias or job. When updating older generated workflows, update job IDs, needs and setup output references together; keep original keys in PTk configuration and let the generator wire matrix outputs and dependencies.
3. Inspect actual output-producing commands and explicitly declare useful files/directories on their producing steps or job, with optional `artifact_type`. See [job authoring](../ptk-job-authoring/SKILL.md) and [artifact manifests](../../../docs/guides/artifacts.rst). Never infer outputs from a build folder or add cache merely for uploads. Require portable, disjoint repository-relative destinations; do not declare both a directory and its child. Use a stable output filename when a tool supports it. Do not invent output globs or a separate PTk `inputs` mapping.
4. Inspect `artifactory_paths.ptk.yml`: base URL, repository, event routes and job suffixes. All producers of one workflow must upload to one server and repository. Actual paths come from completed jobs, not setup. Inspect or author `cx.ptk.yml`: `technical_user`, `runner_group`, `image` (default `docker.image`), `artifactory_credential` (default `docker.credential`), `pmt.version` and, for VMR members, `vmr` (manifest URL, GitHub App ID, private-key secret name, owner). Ask for missing values; never insert live credentials or invented service URLs. Secret names follow `<PROJECT>_<TECHNICAL_USER>_<CREDENTIAL>_<FIELD>`; list the secrets the user must create.

## Generate and review

5. Run `ptk validate`, then `ptk maintainer gen-workflows NAME` with the discovered repository prefix. It writes `call-NAME.yml` and one `call-<job>.yml` per job (`call-<alias>-<job>.yml` for jobs of other VMR repositories) in the owner's `.github/workflows`. Files with the generated marker line are replaced; files without it are left alone with a warning. Use `--replace-unmarked` only when the user wants hand-written files replaced: it backs them up to `.github/workflows_backup/<date>/` first. A reworked job workflow stays reusable when the marker line is removed and its inputs are kept. Generating files does not dispatch jobs or transfer artifacts.
6. Keep `on: workflow_call`. The `setup` job runs `ptk maintainer matrix --workflow NAME --format github`; every entry declares `needs: [setup, ...producer_invocations]`, guards on `has_jobs_<invocation>` and calls its job workflow with the setup matrix, `toJSON(needs)`, `max-parallel`, `continue-on-error` and `secrets: inherit`. Never use the last-finishing matrix job's outputs to identify a producer. GitHub `max-parallel` limits each matrix, not the whole workflow.
7. In each job workflow, preserve: checkout, `safe.directory`, for rows with producers `ptk maintainer cx download`, then `ptk run` and `ptk maintainer cx upload`. JSON and secrets reach PTk only through environment variables. Never invoke `ptk workflow run` in CX.
8. The Linux job container must already contain a matching PTk release, Bash, Git, curl and project tools. Pass `additional-properties` as JSON without overriding producer identity. Pin `pmt.version` to an approved tag or commit. For readable uploads set `name` in `artifactory_paths.ptk.yml` (e.g. `${run.job}_${run.variant}_${version.current.value}`); files then land in the destination as `<name>[_<artifact_type>].zip` with `<name>.ptk-manifest.json`.
9. VMR members check out with PMT `checkout-or-repo-init` and the configured GitHub App, or with `cx.checkout` (a project-owned step); the callable workflow accepts `manifest-branch` and `checkout-ref`. The workflow owner directory is the default `project-directory`; matrix working directories and mapped producer variants come from setup. Downloads restore paths beneath the producing repository. Checkouts include history and tags for Git-based versions.

## Validate and hand off

10. Inspect the generated graph and action wiring against the PTk workflow. Preview `matrix --workflow NAME` in an appropriate context only after checking configured version commands: matrix export can execute version discovery. A local maintainer can use `--cx` and `--event EVENT` for a relevant preview. Do not bypass role checks or change maintainers to run validation. Use YAML/action linting when available; a parsed file alone does not prove hosted execution succeeds.
11. Download restores every output in each selected producer manifest; `artifact_type` labels do not provide a built-in type filter. Directories transfer as ZIP; restores verify SHA256 and identity and return original relative paths. Scope is the GitHub repository/run ID. Missing manifests, unsafe paths, symlinks and overlapping restores across producers fail. Successful earlier steps may expose artifacts after later failure; whole-job outputs require complete success. Project authors own artifact correctness, retention and cache decisions.
12. Report the workflow path, dependency/variant mapping, declared outputs, completed checks and remaining TODOs. Distinguish generation, local validation and actual hosted execution. Running the pipeline, accessing secrets or uploading artifacts needs to be within the user's requested scope. Do not dispatch a workflow simply to prove the template was written.

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
including mapped repository variants. Generation replaces only files with the
generated marker. Do not claim hosted execution from
local validation alone. Read the linked execution and GitHub workflow docs for details.
