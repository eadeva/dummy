# Step Reference

The full step reference has moved. Every step type registered with `StepRegistry` is now documented in a dedicated per-category page under [`steps/`](steps/index.md).

## Where to go next

- **Browse by category:** [Steps index](steps/index.md) — the canonical entry point. Includes the registry mechanism, base-class fields, special-behaviour index, and resource-pool keys.
- **Jump directly to a category:**
  - [Build wrappers](steps/build_wrappers.md) — `cmake_*`, `make`, `bazel_*`, `ctest`
  - [Conan / package management](steps/conan.md) — `conan_command`
  - [Shell, files & variables](steps/shell_files_vars.md) — `shell_run_command`, `custom_script`, `file_*`, `dir_find`, `variable_*`
  - [Interactive](steps/interactive.md) — `choice`, `user_input`
  - [Timers & threads](steps/timers_threads.md) — `timer_*`, `wait_idle`, `thread_stop`
  - [Quality & analysis](steps/quality.md) — `docascode`, `oss`, `qac`, `sca`, `sfa`
  - [TACO test selections](steps/taco.md) — `taco_filter`, `taco_ctest`, `taco_robotfw`
  - [Deploy & reports](steps/deploy_reports.md) — `deploy`, `artifactory_cleanup`, `test_report_collect`
  - [ELF & binary](steps/elf_binary.md) — `elf_*`, `bin_*`
  - [TRACE32](steps/t32.md) — `t32_*`
  - [WinIDEA / iSYSTEM](steps/winidea.md) — `winidea_*`
  - [CANoe](steps/canoe.md) — `canoe_*`
  - [Power supplies](steps/power.md) — `power_supply_*`, `voltcraft_*`
  - [Serial / COM](steps/com.md) — `com_*`
  - [Network — SSH & TFTP](steps/network.md) — `ssh_*`, `tftp_*`
  - [Artifactory](steps/artifactory.md) — `art_*`
  - [Vendor / code gen & Toolbase](steps/vendor.md) — `vector_davinci_*`, `tresos_*`, `dng_export`, `tb_installation`

## Why the split?

The previous monolithic page (~1700 lines) was unwieldy to navigate and slow to render. The per-category split keeps each page focused on a single concern, while [`steps/index.md`](steps/index.md) provides the common context (registry, base class, conventions) that all steps share.
