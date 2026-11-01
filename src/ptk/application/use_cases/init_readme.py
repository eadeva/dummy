"""PTK-generated introduction placed alongside the initialized configuration."""

from pathlib import Path


def configuration_readme(folder: Path) -> str:
    if folder.parts[:2] in (
        (".github", "ptk"),
        (".github", "skills"),
        (".github", "agents"),
    ):
        from ...domain.errors import PtkError

        raise PtkError(
            "configuration directory conflicts with the managed assistant bundle"
        )
    root = "../" * len(folder.parts)
    return TEMPLATE.replace("@ROOT@", root)


TEMPLATE = """# PTK configuration

This directory contains this repository's Project Toolkit (PTK) configuration.
PTK provides a shared CLI and VS Code experience for jobs, variants, local
workflows, diagnostics and artifact handoff. Project commands and tools perform
and validate the actual work.

## Start here

Run commands from the repository root or one of its subdirectories:

```bash
ptk --help
ptk validate
ptk -V debug run hello --dry-run
```

The last command previews a starter job created by `ptk init`. Replace the starter
jobs, variants and component with your project's configuration. Use a dry run to
inspect commands and the dependency graph before executing an unfamiliar job.
The Project Toolkit VS Code extension provides configuration forms, graphs and
job launch controls; use it with the matching installed PTK runtime.

## Configuration ownership

The repository's [entry file](@ROOT@.main.ptk.yml) selects this directory through
`repository.config_path`. Files contain their section body; filenames supply
job, workflow and variant names. There are no implicit local/CX overlays.

- [project.ptk.yml](project.ptk.yml): project settings and component registration.
- [jobs/](jobs/): commands, parameters, step dependencies and declared outputs.
- [workflows/](workflows/): local orchestration of jobs through `needs`.
- [variants/](variants/) and [project.variants.ptk.yml](project.variants.ptk.yml):
  variant selections and defaults; component features live beside their code.
- [tools.ptk.yml](tools.ptk.yml), [versioning.ptk.yml](versioning.ptk.yml),
  [configs.ptk.yml](configs.ptk.yml) and [credentials.ptk.yml](credentials.ptk.yml):
  tool, version, external-policy and credential declarations.
- [maintainers.ptk.yml](maintainers.ptk.yml): maintainer login IDs, not Git emails.

Keep secrets out of committed configuration. External synchronized base files
belong to their source repository; project-owned overlays remain separate.
This README is managed by PTK and refreshed by `ptk maintainer sync agent`.
Local edits are protected by the same conflict checks as the agent and skills.
Keep repository-specific guidance in a separate document.

## Execution and outputs

Use `needs` for ordering; declaration order does not serialize independent work.
Use `when` for conditions. Job conditions use portable CX/variant context;
runner-specific conditions belong on steps. CX mode is detected automatically;
`PTK_CX` overrides detection, while `--cx` / `--no-cx` are maintainer-only switches.

Every declared output is required. Missing outputs fail their producer and block
consumers; projects still own artifact contents and freshness. Declare outputs
primarily for workflow uploads/downloads. PTK cache is an optional aid enabled
with `cache: true`; correctness remains the project's responsibility.
`--no-cache-ptk` disables reuse throughout an execution.

PTK workflows orchestrate local runs. Generated GitHub workflows run individual
PTK jobs after a matrix setup job. All configured jobs remain in the YAML;
job conditions filter their variant rows. Runners, Docker images, checkout,
credentials and workflow callers remain project-owned.

## Agent, skills and offline reference

`ptk init` installs the version-matched assistant bundle in this repository:

- [PTK expert agent](@ROOT@.github/agents/ptk-expert.agent.md): entry point for
  assistant-guided PTK work.
- [PTK skills](@ROOT@.github/skills/): focused authoring and troubleshooting guidance.
- [Job authoring](@ROOT@.github/skills/ptk-job-authoring/SKILL.md),
  [DevOps](@ROOT@.github/skills/ptk-devops/SKILL.md) and
  [GitHub workflows](@ROOT@.github/skills/ptk-github-workflows/SKILL.md).
- [Offline documentation](@ROOT@.github/ptk/README.md) and
  [configuration schema](@ROOT@.github/ptk/config-schema.json).

Ask your assistant to read the expert agent or the relevant skill first.
Automatic discovery depends on your editor/assistant; installation does not
execute skills or grant permissions. The bundled examples are references,
not additional jobs configured in this repository.

After upgrading PTK, maintainers can refresh the managed bundle with
`ptk maintainer sync agent`. Locally edited managed files cause conflicts rather
than being silently overwritten. Keep project-specific instructions separately.
Commit the configuration and assistant bundle so colleagues receive them.
"""
