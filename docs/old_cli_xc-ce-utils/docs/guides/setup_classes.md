# Setup & CLI Command Classes

This guide explains the setup-related subcommands shipped by
`xc_ce_utils`, who is allowed to run them, and how the role-gating
mechanism works across `config` and `config-devops`.

The intent is simple:

* **Developers** should never accidentally regenerate files that are
  meant to live in version control (Copilot instructions, shared VS Code
  configuration, MCP launcher JSON). Those are owned by the build-system
  maintainers and ship as committed assets.
* **Developers** still need a way to refresh things that live on their
  workstation only — VS Code extensions, git hooks — without touching
  committed files.
* **Maintainers** need to be able to do everything, ideally without
  remembering yet another secret incantation.

---

## The three buckets

### 1. Automatic (no command needed)

These run as part of `--first-time-setup` or whenever the bootstrap
detects drift. They never need an explicit invocation:

* Conan profile / cache provisioning
* Bazel workspace + disk cache
* Git LFS, git hooks, `.gitconfig` decorations
* Devmate PAT setup

If something in this bucket fails it is retried on the next bootstrap
(`CLI_UNAVAILABLE`) or held back for three weeks (`FAILED`).

### 2. Developer self-service (visible to everyone)

| Command                                  | Effect                                              |
|------------------------------------------|-----------------------------------------------------|
| `./build.ps1 config refresh-hooks`       | Reinstall the git hooks locally (no committed config regeneration) |
| `./build.ps1 config vs-code refresh-extensions` | Install / update the VS Code extensions (not done automatically by the setup) |
| `./build.ps1 config vs-code devmate-setup` | Refresh DEVMATE PAT setup workflow                |
| `./build.ps1 config refresh-bazel-cache` | Refresh local Bazel cache configuration             |
| `./build.ps1 config force-setup`         | Re-run setup using developer-safe setup steps only  |
| `./build.ps1 config clean-older-versions`| Remove older setup folders and installed `xc-ce-utils` versions |
| `./build.ps1 config validate`            | Validate the config tree                            |
| `./build.ps1 config dump-config`         | Dump the merged configuration                       |

None of these mutate files under version control. They are safe for any
developer to run at any time.

### 3. Maintainer-only (hidden from non-maintainers)

These regenerate committed files. They are **hidden** from `--help` for
non-maintainers and **fail closed** if a non-maintainer somehow invokes
them anyway:

| Command                                            | Regenerates                                                       |
|----------------------------------------------------|-------------------------------------------------------------------|
| `./build.ps1 config-devops full-setup`             | Full setup reset including maintainer setup behavior              |
| `./build.ps1 config-devops clang-setup`            | Clang installation + regenerate repository clang config artifacts |
| `./build.ps1 config-devops hooks-setup`            | Full git-hooks setup + regenerate committed `.pre-commit-config.yaml` / `.ruff.toml` |
| `./build.ps1 config-devops vs-code regen-copilot`  | `.github/copilot-instructions.md` and per-topic instruction files |
| `./build.ps1 config-devops vs-code regen-ws-conf`  | `.vscode/extensions.json`, `tasks.json`, `settings.json` (shared) |
| `./build.ps1 config-devops vs-code regen-mcp-json` | `.vscode/mcp.json` for Bosch MCP server launchers                 |

Developers still get local clang toolchain/environment setup during normal setup runs; repository clang config regeneration stays maintainer-gated.

---

## How the gating works

### The `maintainers:` list

The authoritative list of maintainers lives at the top of
[`config/main_conf.yml`](../../config/main_conf.yml):

```yaml
# Users in this list see and can run the maintainer-only commands
# (config-devops full-setup/hooks-setup and config-devops vs-code regen-*). All entries are case-insensitive.
# Non-maintainers can still call those commands explicitly via the
# XC_CE_UTILS_FORCE_MAINTAINER=1 environment variable, e.g. from CI.
maintainers:
  - ADE7PL
```

* Entries are case-insensitive — they are lower-cased on load.
* Missing key, empty list, or a non-list value all mean "no
  maintainers" — every maintainer-only command stays hidden and refuses
  to run.

The current user is read from the OS (Windows: `USERNAME`, POSIX:
`USER`) and lower-cased for comparison.

### The `XC_CE_UTILS_FORCE_MAINTAINER` escape hatch

For CI runners, container images, or emergency local use, the gate can
be forced open by setting the environment variable to any of
`1`, `true`, `True`, or `yes`:

```powershell
$Env:XC_CE_UTILS_FORCE_MAINTAINER = "1"
./build.ps1 config-devops vs-code regen-copilot
```

Any other value (empty, `0`, `false`, `no`, whitespace) leaves the gate
in its normal fail-closed state.

### Behaviour summary

|                                  | Visible in `--help` | Callable        |
|----------------------------------|---------------------|-----------------|
| User in `maintainers:` list      | ✅                  | ✅              |
| `XC_CE_UTILS_FORCE_MAINTAINER=1` | ✅                  | ✅              |
| Anyone else                      | ❌                  | ❌ (clear error)|

The error message points at both the config file and the env var, so
the user always knows how to remediate.

---

## Implementation pointers

* Gate logic: `xc_ce_utils/core_engine/cli/role_gating.py`
* Command wiring: `xc_ce_utils/core_engine/cli/command_factory.py`
* Action-level `requires_role: maintainer` honoring:
  `xc_ce_utils/core_engine/cli/generator.py` (`DynamicCLIGenerator.create_cli`)
* Backing logic for the regen commands:
  `xc_ce_utils/core_engine/cli/vs_code_setup.py`

Unit tests:

* `tests/unit/test_role_gating.py` — gate semantics
* `tests/unit/test_command_visibility.py` — `config`-group wiring
