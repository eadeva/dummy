"""PTk-generated introduction placed alongside the initialized configuration."""

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


TEMPLATE = """# Project Toolkit: developer guide

Project Toolkit (PTk) provides this repository's common interface for running
jobs, choosing variants, orchestrating local workflows and inspecting reports.
This directory contains the project-owned configuration behind those commands.

## For developers

### Install PTk

Use the installation script included in this repository. From the repository
root, run the command for your platform:

Linux:

```bash
sh .github/ptk/install/install.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .github/ptk/install/install.ps1
```

The scripts install uv if needed, install or update PTk, and set up shell
completion and the bundled VS Code extension when supported. Follow their
terminal instructions, then open a new terminal if `ptk` is not yet on PATH.
Use your project's approved package source and credentials. Maintainers should
provide `PTK_SOURCE` when a specific package version or source is required;
otherwise these copied scripts install `ptk` from the configured package index.
See the [shell installer](@ROOT@.github/ptk/install/install.sh) and
[PowerShell installer](@ROOT@.github/ptk/install/install.ps1) for available options.

### Start with help and self-service

From the repository root or one of its subdirectories, start with:

```bash
ptk --help
ptk help
ptk self-service
```

Use `ptk --help` for available commands, jobs and workflows; `ptk help` for the
project's help page; and `ptk self-service` to discover developer setup and
support commands for tools, hooks, credentials and environment checks.

For guided work, start with the **[PTk expert agent](@ROOT@.github/agents/ptk-expert.agent.md)**
and the **Project Toolkit VS Code extension**. Ask your assistant to read the
expert agent before working on this repository's PTk configuration. It points
to the relevant [skills](@ROOT@.github/skills/) for focused tasks; you can also
select a skill directly. Automatic agent/skill discovery depends on your editor.

### Use the Project Toolkit extension

The **Project Toolkit VS Code extension** is the recommended interface for
running and configuring jobs and workflows. It provides a configuration tree,
guided forms, dependency graphs, variant and parameter selection, and report
access. Use it with the matching installed PTk runtime. See the
[extension guide](@ROOT@.github/ptk/docs/guides/editor.rst) for installation and usage.

Start with the project's existing jobs and workflows. Preview unfamiliar work
with a dry run, inspect the dependency graph, then execute the selected variant.
Use the generated reports and diagnostics to investigate failures.

### Run from the terminal

From the repository root or one of its subdirectories:

```bash
ptk validate
ptk run JOB --dry-run
ptk -V VARIANT run JOB
ptk workflow run WORKFLOW --dry-run
ptk workflow run WORKFLOW
```

Replace `JOB`, `VARIANT` and `WORKFLOW` with names configured in this repository.
Omit `-V` to use the project's default selection. PTk workflows run locally;
CX pipelines execute individual jobs. Consult `ptk JOB --help` for job parameters.
Use `--no-cache-ptk` when you need to bypass PTk output reuse.

### Add or change jobs and workflows

Prefer the extension's configuration forms and graphs for creating jobs, choosing
command or Python modes, documenting parameters and connecting dependencies.
Raw YAML remains available when needed. The owning files are in [jobs/](jobs/)
and [workflows/](workflows/); each filename supplies its entity name.

Use `needs` for ordering; independent work may run concurrently. Use `when` for
conditions. Job conditions use portable CX/variant context; runner-specific
conditions belong on steps. Declare the files or folders your commands produce:
every declared output is required, and missing outputs fail the producer and
block consumers. Your commands remain responsible for contents and freshness.

Validate configuration and preview affected jobs/workflows before execution.
For guidance, ask your assistant to use the
[job authoring skill](@ROOT@.github/skills/ptk-job-authoring/SKILL.md) or
[workflow authoring skill](@ROOT@.github/skills/ptk-workflow-authoring/SKILL.md).
Read [local setup and troubleshooting](@ROOT@.github/ptk/docs/guides/local-setup.rst)
when hooks, tools or credentials prevent a run.

## For maintainers and DevOps

### Maintain project configuration

The repository's [entry file](@ROOT@.main.ptk.yml) selects this directory through
`repository.config_path`. Files contain their section body. There are no implicit
local/CX overlays. The extension is also recommended for reviewing and editing
these settings against the installed runtime's schema.

- [project.ptk.yml](project.ptk.yml): project settings and component registration.
- [variants/](variants/) and [project.variants.ptk.yml](project.variants.ptk.yml):
  selections and defaults; component features live beside their code.
- [tools.ptk.yml](tools.ptk.yml) and [versioning.ptk.yml](versioning.ptk.yml):
  tool declarations and version sources.
- [configs.ptk.yml](configs.ptk.yml): external policy sources and project overlays.
- [credentials.ptk.yml](credentials.ptk.yml): credential declarations, never secrets.
- [maintainers.ptk.yml](maintainers.ptk.yml): maintainer login IDs, not Git emails.

Keep external synchronized bases unchanged; maintain project overlays separately.
After configuring external sources and file mappings in `configs.ptk.yml`, use:

```bash
ptk maintainer sync configs --diff
ptk maintainer sync configs
ptk maintainer sync configs --check
```

`--diff` previews changes, the command without flags synchronizes enabled groups,
and `--check` validates local files without fetching. This synchronizes external
base configurations; `ptk maintainer sync agent` updates the README, installers
and assistant resources. Commit synchronized bases and their provenance record.
See the [external configuration guide](@ROOT@.github/ptk/docs/guides/shared-configs.rst)
for source revisions, project overlays and local-edit protection.

CX mode is detected automatically. `PTK_CX` overrides detection, while
`--cx` / `--no-cx` are maintainer-only switches. See the
[configuration guide](@ROOT@.github/ptk/docs/guides/configuration.rst) and
[DevOps skill](@ROOT@.github/skills/ptk-devops/SKILL.md).

### Set up a new repository

If PTk is not installed yet, obtain `install/install.sh` or `install/install.ps1`
from the PTk source repository at your approved release and run it locally.
Set `PTK_SOURCE` to your approved package/version or source as needed, and
configure access to your package index before installation. A PTk source checkout
is installed directly when its own installer runs without `PTK_SOURCE`.

For a repository without PTk configuration, use
`ptk init --config-dir config/ptk` (choose the directory for that project).
This creates starter configuration, this README, the assistant bundle and both
installation scripts under `.github/ptk/install/` for colleagues to use.
Review and adapt the starter jobs, variants and component before committing.
Existing configured repositories do not need this command; use the sync commands
below to update their managed documentation and assistant resources.

### Set up CX workflows and artifacts

Use `ptk maintainer gen-workflows` to generate callable GitHub workflow templates.
A setup job exports the variant matrices; subsequent jobs download producer
artifacts, run one PTk job and upload its declared outputs. All configured job
definitions remain in the YAML; job conditions filter their variant rows.
Existing workflow files are not overwritten.

Review dependencies, variant mappings, required outputs and artifact destinations.
Provide the project's runners, Docker images, checkout, credentials and caller
workflows/events. See the
[GitHub workflow skill](@ROOT@.github/skills/ptk-github-workflows/SKILL.md) before
changing generated templates or transfer wiring.

Outputs primarily describe artifacts for workflow uploads/downloads. PTk cache is
an optional aid enabled with `cache: true`; cache correctness and artifact
freshness remain project responsibilities. Declaring paths does not transfer files.

### Keep the assistant reference current

The repository includes the [PTk expert agent](@ROOT@.github/agents/ptk-expert.agent.md),
[focused skills](@ROOT@.github/skills/),
[offline documentation](@ROOT@.github/ptk/README.md) and
[configuration schema](@ROOT@.github/ptk/config-schema.json).
Ask your assistant to read the expert agent or relevant skill first. Automatic
discovery depends on the editor/assistant. Bundled examples are references, not
additional jobs configured in this repository.

After upgrading PTk, refresh this README, installation scripts and the managed
assistant bundle with:

```bash
ptk maintainer sync agent --check
ptk maintainer sync agent
```

Unchanged managed files update automatically; local edits produce conflicts rather
than being silently overwritten. Keep repository-specific guidance separately.
Commit configuration and assistant-reference updates so colleagues receive them.
"""
