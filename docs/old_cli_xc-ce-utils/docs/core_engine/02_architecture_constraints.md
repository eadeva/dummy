# 2. Architecture Constraints

## 2.1 Technical Constraints

| Constraint | Rationale / Impact |
|---|---|
| Python ≥ 3.10 | Language baseline; `pyproject.toml` targets 3.12 for the PyInstaller build. |
| Distributed as a PyInstaller-frozen executable (`config/pyinstaller/xc-ce_core-engine.spec`) | Any new module reachable only via dynamic `importlib.import_module()` calls must be added to the spec's `hidden_imports` (or covered transitively by an existing `collect_submodules` entry) or it silently won't be bundled. |
| No pre-installed Python required on target machines | `build.ps1` / `build.sh` bootstrap the matching frozen executable version; core_engine itself must not assume a live pip/uv environment at runtime. |
| Fast `--help` / `--version` | Lazy `import_module()` calls gate heavy imports (full step registry, Sphinx toolchain, etc.) behind an `_is_metadata_request()` check in `cli/generator.py`. |
| Windows-primary, Linux-aware | Platform-specific tool installation (toolbase/choco vs. Linux packages) is isolated in `application/orchestration/tool_requires_installer.py`; hardware-adapter steps (Trace32, WinIDEA, CANoe, power supplies) are inherently Windows-only. |
| Ruff-enforced style | `config/ruff/base.toml` (line-length 80, single quotes, preview-mode rule set including complexity/pylint-refactor rules) is regenerated into every consumer repo's `.ruff.toml` on setup; core_engine itself must comply. |
| Configuration schema validated via Pydantic v2 | `core_engine/config/config_models.py` — YAML structure changes must stay schema-compatible or bump a documented breaking change. |

```{note}
`config/` paths in this table are the common **default** location, not guaranteed — the actual
config root is the parent directory of wherever `main_conf.yml` resolves (overridable per
project via `.xc-ce-utils`). See [main_conf.yml's Discovery
Order](../guides/config_files/main_conf.md#discovery-order).
```

## 2.2 Organizational Constraints

| Constraint | Rationale |
|---|---|
| No legacy compatibility shims | As of the clean-architecture migration (2026-07), there is exactly one canonical import path per symbol — no re-export indirection files, no flat legacy module paths. New code must not reintroduce this pattern (enforced by `test_legacy_compatibility_wrappers_are_removed`). |
| Single stable driving-adapter boundary | Any driving adapter (the `cli/` package today, potentially a future `gui/` package) may only import from `core_engine.application` (the top-level public API) and `core_engine.domain` (shared vocabulary) — never `core_engine.adapters` or `application.{orchestration,facades,use_cases}` submodules directly. Enforced by `test_cli_layer_only_uses_application_public_api_and_domain`. |
| Domain has zero upward dependencies | `core_engine.domain` must not import from `application`, `adapters`, or `cli`. Enforced by `test_domain_layer_has_no_upward_imports`. |
| Cross-repo consumers | `core_engine.domain.*` symbols are consumed directly by other xc_ce_utils modules (`clang`, `git_hooks`, `tool_installers`, `vector_generation`, `vs_code_configurator`, `docascode`, `auth`) and by external consumer repos (e.g. Toyota Sphinx `conf.py` files) — changes to `domain` module paths are breaking changes for those consumers. |
