# 6. Runtime View

## 6.1 Single-variant build invocation

```text
1. xc-ce-utils <action> -var <alias>          (or python -m xc_ce_utils.core_engine.cli.entrypoint)
2.   cli/entrypoint.py: create_dynamic_cli()
3.     cli/platform_setup.py: console/PATH/env fixes, dev-tooling provider config
4.     cli/environment_setup_orchestrator.py: run_environment_setup() (skipped for --help/--version)
5.     cli/generator.py: DynamicCLIGenerator — load runtime config via
       core_engine.application.load_runtime_config(); build VariantMatrix; wire action commands
6. click dispatches to the action command
7.   cli/variant_executor.py: execute_action_with_arguments()
8.     core_engine.application.execute_action(generator, action, options, runtime)
9.       application/facades/execution.py: resolves single vs. multi-variant path
10.        core_engine.application.ExecutionAction(config)              [application/orchestration/action_orchestrator.py]
11.        ExecutionAction.run()
12.          .setup()
13.            clean/create folders; handle --clean/--rebuild/--no-cache
14.            application/orchestration/tool_requires_installer.py: install tool_requires
15.          .execute_action()
16.            for each phase in [from_phase, to_phase]:
17.              application/orchestration/step_executor.py: create_step() → StepRegistry.get(type)
18.              step_executor.execute(step) → step.run() → recovery routing (error_recovery.py)
19.          finally: _run_unified_reporting()
20.            reporting/adapters/execution_log_reporter.py: ExecutionLogReporter.run_unified_reporting()
21.        finally: _release_resources()                                [adapters/execution/resource_manager.py]
22. On BuildError: application/orchestration/debug_artifact_uploader.py uploads CI debug artifacts
```

```{uml} ../_diagrams/build_flow_diagram.puml
:caption: ExecutionAction.run() activity flow — setup, phase/set execution with error recovery, unified reporting, and debug-artifact upload on failure.
```

## 6.2 Multi-variant parallel dispatch

When `-all`/`--all-variants` or a comma-separated `-var` list is given,
`application/facades/execution.py::_execute_multi_variant_action` resolves the allowed variants
(`cli/variant_executor.py::get_variants_to_execute`), then spawns one subprocess per variant via
`ThreadPoolExecutor` — each subprocess re-invokes the same CLI binary
(`build_python_command()` in `cli/variant_executor.py`) with a single resolved variant alias.
Worker count is capped by `get_max_parallel_builds()` (CI: 2; local ≤4 variants: one per variant;
local >4 variants: 30–50% of CPU cores clamped to `[2, 8]`; overridable via `MAX_PARALLEL_BUILDS`).

## 6.3 First-run environment bootstrap

Before any action executes (and skipped entirely for `--help`/`--version`/setup-only commands),
`cli/environment_setup_orchestrator.py::run_environment_setup()` ensures the Conan environment is
initialized, then — unless `XC_CE_SETUP_DONE` is already set — runs the full
`EnvironmentSetup.run_setup()` phase chain (`setup/phases/*`: credentials, Conan, Bazel, clang,
git hooks, VS Code, DevMate). See [Environment Setup Flow](reference/environment_setup_flow.md)
for the authoritative phase-by-phase sequence.

## 6.4 Step execution lifecycle

```python
def run(self):
    self.validate()  # config validation (override in subclass)
    self.pre_processing()  # start timer, wait_idle_before
    self.execute()  # abstract — the actual work
    self.post_processing()  # wait_idle_after, stop timer
```

When `log_enabled=True` (default), `execute()` is wrapped in `logger.file_scope()`, capturing all
output to `<log_folder>/<step_name>.log` (and a parallel `.jsonl` consumed by
`ExecutionLogReporter`).
