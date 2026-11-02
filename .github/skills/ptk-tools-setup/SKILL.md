---
name: ptk-tools-setup
description: "Configure or troubleshoot required tools and installation in a PTK project, including missing or incompatible tools, selected PATH, Docker policies and local onboarding. Discover supported installer fields; do not assume the project uses PTK\u2019s development toolchain."
---

# ptk-tools-setup

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [docs/guides/configuration.rst](../../../docs/guides/configuration.rst) and [docs/reference/cli.rst](../../../docs/reference/cli.rst); use `ptk describe --json --configuration` (or the bundled schema when runtime inspection is unavailable) for tool fields.

2. Inspect the selected job's inherited tool requirements and platform-specific definitions. Reuse existing tool keys and sources; declare a check command, version range and version_regex matching observed output.

3. Add job requires_tools so missing or wrong tools are caught before execution.

4. Configure platform-appropriate sources: Chocolatey on Windows, uv_tool, verified downloads, optional apt/dnf.

5. Prefer SHA-256 checksums for downloads and verify the archive's bin subfolder.

6. Run `ptk self-service tools --job JOB --dry-run` and inspect the proposed installations.

7. Use `ptk self-service tools --job JOB` or the job's `--setup` only within the requested installation scope.

8. Treat system installs and Chocolatey bootstrap as explicit options; do not add them merely to bypass failures.

9. Verify with `ptk self-service doctor` and rerun the tool's check. Use `ptk maintainer sync configs` for shared configuration and `ptk self-service hooks install` for hooks.

10. For a configuration change, verify the selected tool check and resolved executable, not PTK internal adapter tests. Only PTK developers change/test adapters in its source checkout.

11. Global and job `requires_tools` merge per tool: unmentioned tools stay inherited, `name: false` disables one, and settings mappings override only that job. Tool files load automatically; see [docs/guides/configuration.rst](../../../docs/guides/configuration.rst).

Managed installations coexist by version/source identity. Verify the job-selected PATH; never append the entire cache. System installers remain host-shared. Use `environment.keep` for required host variables; PATH inheritance is a separate opt-in.


Only when the project uses Toolbase, declare an exact package/version and relative executable directories; it is Windows-only. Toolbase-only entries are ignored on Linux. Do not add global PATH or shared `.env` mutations, and leave live Toolbase validation to the user's Windows environment.

Only when the project uses Artifactory, configure the HTTPS base URL, repository and exact path/name or AQL properties. The adapter uses curl, not JFrog CLI. Require a checksum (explicit or from AQL), default to unique selection, and provide bearer credentials through `token_env`, never YAML values. ZIP/tar and standalone files are supported; legacy 7z bundles require conversion.

For generated GitHub workflows, supply a Linux container image with matching PTK, Python 3.12+, Bash, curl and project tools already installed. The shipped artifact/run Actions do not install PTK. See [GitHub workflows](../ptk-github-workflows/SKILL.md).

Consult [local setup](../../../docs/guides/local-setup.rst) for the preparation order and hook behavior. `tools.ensure` defers initial required-tool checks; order it before consumers with explicit `needs`. Unknown executables in arbitrary commands are not discovered as tool requirements. Mise is not a built-in installer; do not invent a `mise` schema field.

`docker: false` is the default and disables installation only inside Docker. Keep version checks, report entries and existing tool activation. Use `docker: true` only when installation inside the image is intended. `PTK_DOCKER=1|0` overrides best-effort runtime detection. Report every unavailable/incompatible tool with its recorded reason; direct the developer to correct the image or its selected PATH rather than disabling checks.
