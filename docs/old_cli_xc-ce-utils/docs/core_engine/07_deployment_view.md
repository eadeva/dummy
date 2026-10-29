# 7. Deployment View

## 7.1 Distribution model

`core_engine` is not distributed as a plain Python package to end users — it is bundled, together
with the rest of `xc_ce_utils`, into a **PyInstaller-frozen executable**
(`config/pyinstaller/xc-ce_core-engine.spec`, profile `core-engine`) so that consumer
repositories/CI agents do not need a pre-existing Python environment.

```text
build.ps1 / build.sh  (consumer repo, or xc_ce_utils itself)
   │  resolves/bootstraps the matching xc-ce-utils version
   ▼
_bin/<variant>/<action>/xc-ce-utils/          (onedir PyInstaller bundle)
   ├── xc-ce-utils.exe                        (bootloader)
   ├── bin/uv.exe, bin/uvx.exe                (bundled sidecars for pre-commit `uvx ...` hooks)
   └── ... (PYZ archive, DLLs, data files)
```

## 7.2 Build-time artifact layout (building `xc-ce-utils` itself)

| Path | Contents |
|---|---|
| `_builds/<variant>/xc-ce-utils/venv_xc-ce_core-engine/` | Ephemeral `uv`-managed virtualenv used only to run PyInstaller. |
| `_builds/<variant>/xc-ce-utils/xc-ce_core-engine/` | PyInstaller work directory (`PYZ-00.pyz`, `warn-*.txt`, `xref-*.html`). |
| `_bin/<variant>/xc-ce-utils/` | Final frozen executable output (`COLLECT` stage). |
| `_logs/<variant>/xc-ce-utils/` | Per-step text + JSONL logs for the build action itself. |
| `_reports/<variant>/xc-ce-utils/` | Unified report artifacts (`*.canonical.json`, `*.html`) for the build action. |

## 7.3 Runtime execution context

| Context | Notes |
|---|---|
| Local developer machine | `REPO_PATH` defaults to CWD; environment isolation trims `PATH` to a curated allowlist before running the frozen executable's step logic. |
| CI (GitHub Actions / Jenkins) | Detected via `is_running_in_ci()`; gates debug-artifact upload, worker-count defaults, and CI-only action visibility. |
| Docker | `RuntimeContext.is_docker` gates toolbase/choco/Linux-package installation (assumes pre-installed tools inside the image). |

## 7.4 PyInstaller hidden-imports maintenance

Because many core_engine submodules are loaded via dynamic `importlib.import_module()` calls
(for fast `--help`/`--version` startup — see [ch. 2](02_architecture_constraints.md)), the spec
file maintains two complementary mechanisms:

1. `core_engine_modules` — a short list of top-level packages passed to `collect_submodules()`,
   which recursively bundles every `.py` file underneath (e.g. the bare `'xc_ce_utils.core_engine'`
   entry already covers `cli/`, `domain/`, `application/`, `steps/`, etc.).
2. `hidden_imports` — an explicit, flat list of individual modules, kept in sync with new
   architecturally-significant modules (e.g. each new `application/orchestration/*.py` file added
   here as it was created) as a belt-and-suspenders safety net.

When adding a new top-level package under `core_engine/`, prefer adding one entry to
`core_engine_modules` (covers everything recursively) over enumerating every file in
`hidden_imports`.
