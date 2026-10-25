---
name: ptk-tools-setup
description: Declare tool checks and installers or diagnose ptk setup, doctor and
  onboarding.
---

# ptk-tools-setup

1. Read [docs/configuration.rst](../../../docs/configuration.rst) and [docs/cli.rst](../../../docs/cli.rst); use `ptk setup config schema` for tool fields.

2. Declare a check command, version range and version_regex matching the actual output.

3. Add action requires_tools so missing or wrong tools are caught before execution.

4. Configure platform-appropriate sources: Chocolatey on Windows, uv_tool, verified downloads, optional apt/dnf.

5. Prefer SHA-256 checksums for downloads and verify the archive's bin subfolder.

6. Run `ptk setup install --action ACTION --dry-run` and inspect the proposed installations.

7. Use `ptk setup install --action ACTION` or the action's `--setup` only within the requested installation scope.

8. Treat system installs and Chocolatey bootstrap as explicit options; do not add them merely to bypass failures.

9. Verify with `ptk setup doctor` and rerun the tool's check. Use `ptk setup self` for project configuration/hooks.

10. Test adapters with fake runners or local archives; do not install machine-wide tools in unit tests.

11. Global and action `requires_tools` merge per tool: unmentioned tools stay inherited, `name: false` disables one, and settings mappings override only that action. Tool files load automatically; see [docs/configuration.rst](../../../docs/configuration.rst).

Managed installations coexist by version/source identity. Verify the action-selected PATH; never append the entire cache. System and plugin installers remain host-shared. Use `environment.keep` for required host variables; PATH inheritance is a separate opt-in.
