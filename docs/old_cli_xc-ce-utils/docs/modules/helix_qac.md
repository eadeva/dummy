# Helix QAC

**Package:** `xc_ce_utils.helix_qac`

XC-CE integration module for Perforce Helix QAC static code analysis.

---

## Purpose

Orchestrates Static Code Analysis (SCA) and Static Flow Analysis (SFA / dataflow) within the XC-CE Utils automation engine. Handles QAC project creation, analysis execution, baseline comparison, report generation, and JQ-based result filtering.

---

## Key Components

- **QAC project management** — create/configure analysis workspaces
- **SCA execution** — full static code analysis runs
- **SFA execution** — dataflow / static flow analysis
- **Baseline comparison** — differential results against stored baselines
- **Report generation** — formatted analysis reports
- **JQ-based filtering** — filter analysis results with JQ expressions
- **SWQ command wrapper** — runs `swq-sca-tools` through `uvx`

---

## Step Types

| Step Type | Description |
|---|---|
| `sca` | Run Static Code Analysis |
| `sfa` | Run Static Flow Analysis (dataflow) |
| `qac` | General QAC operations |

---

## Prerequisites

- Helix QAC toolchain (installed via Toolbase)
- `uvx` available (or bundled sidecar runtime)
- CMake/Ninja for compilation database generation

---

## Typical Workflow

1. **Create workspace** — set up QAC project with source files and compiler settings
2. **Download baseline** (SFA) — fetch `.sup` baseline from Artifactory
3. **Find diff files** (SFA) — identify changed files via `git diff`
4. **Run analysis** — execute SCA or SFA on target files
5. **Compare baseline** — diff results against previous baseline
6. **Generate report** — produce formatted analysis output

---

## Configuration

Analysis configuration is driven by:

- `config/qac/` — QAC datastore and project settings
- `adapt_datastore: true` in `qac` / `sfa` / `sca` steps when datastore templates use `{{ qac_exe_path }}`
- Runtime normalization of legacy `QAC_CONFIG_PATH` values pointing to `_internal/xc_ce_utils/helix_qac`
- Build variant environment variables (`CUSTOMER`, `HW_VARIANT`, `SW_VARIANT`)
- Artifactory credentials for baseline download

---

## See Also

- [Execution Engine](../core_engine/05_building_block_view.md) — build system integration
- [Global Modules](global_modules.md) — command execution utilities
