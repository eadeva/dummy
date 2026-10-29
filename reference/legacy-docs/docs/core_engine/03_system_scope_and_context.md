# 3. System Scope and Context

## 3.1 Business Context

```text
                          ┌──────────────────────────┐
   YAML configuration ──▶ │                          │ ──▶ Frozen executable
   (actions/variants)     │      xc-ce-utils          │      (xc-ce-utils.exe)
                          │   (core_engine + CLI)     │
   Developer / CI  ──────▶│                          │──▶ Build artifacts, reports,
   invocation              └──────────────────────────┘     deployed packages
```

`core_engine` is invoked either directly by a developer (`build.ps1` / `build.sh` /
`xc-ce-utils` on PATH) or by a CI pipeline. It reads project-local YAML configuration and
drives external build/analysis/deployment tools to produce artifacts.

## 3.2 Technical Context

| External system | Interaction | Owned by |
|---|---|---|
| Artifactory | Tool-requires + artifact download, build/report/debug-artifact upload | `adapters/execution/tool_installer_adapter.py`, `adapters/deployment/artifactory_deployer.py` |
| Conan | Dependency/toolchain management | `wrappers/rb_conan_wrapper.py`, `setup/setup_conan.py` |
| Bazel / CMake / Make | Build execution | `wrappers/rb_bazel_wrapper.py`, `rb_cmake_wrapper.py`, `rb_make_wrapper.py` |
| Git | Repository state, commit hash, hooks | `git_hooks/*`, `GitPython` |
| VS Code / GitHub Copilot | Workspace configuration, Copilot instructions, MCP servers | `adapters/dev_tooling/*`, `vs_code_configurator/*` |
| Vector DaVinci, EB tresos | Code generation | `steps/vendor_steps.py` |
| Helix QAC, SonarQube | Static analysis | `steps/quality_steps.py`, `reporting/adapters/importers/*` |
| TRACE32, WinIDEA, CANoe, power supplies, COM/SSH/TFTP | Hardware-in-the-loop test execution | `steps/t32_steps.py`, `winidea_steps.py`, `canoe_steps.py`, `powersupply_steps.py`, `com_steps.py`, `ssh_steps.py`, `tftp_steps.py` |
| Splunk | Log/metrics export | `steps/deploy_steps.py` (`splunk_export`) |
| PyInstaller | Executable packaging | `config/pyinstaller/xc-ce_core-engine.spec` |

## 3.3 Driving Adapters (who calls into `core_engine`)

| Driving adapter | Entry point | Depends only on |
|---|---|---|
| CLI (today) | `xc_ce_utils.core_engine.cli.entrypoint:main` (invoked via `xc_ce_utils.xc_ce_utils:main`) | `core_engine.application` (public API) + `core_engine.domain` |
| GUI (future, not yet implemented) | *n/a* | Same boundary — see [ch. 4](04_solution_strategy.md) and [ADR-2](09_architecture_decisions.md) |

This driving-port boundary is the reason a second front-end can be added without touching
`application`, `adapters`, or `domain`.
