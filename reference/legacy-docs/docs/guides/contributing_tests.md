# Contributing Tests

This guide explains how the `xc-ce-utils` test suite is organised and how to add new tests without breaking the fast-feedback contract.

---

## Suite layout

```
tests/
├── conftest.py           # shared fixtures + optional-dependency stubs
├── unit/                 # pure-logic, no I/O, no subprocess, no network
│   ├── test_config_models.py
│   ├── test_conf_file_loader.py
│   ├── test_env_isolation.py
│   ├── test_env_manager.py
│   ├── test_exceptions.py
│   ├── test_execution_engine_recovery.py
│   ├── test_setup_phases.py
│   ├── test_step_discovery.py
│   ├── test_step_registry.py
│   ├── test_variant_matrix.py
│   ├── test_wrapped_step.py
│   └── test_wrapper_registry.py
└── integration/          # touches FS / subprocess (uses tmp_path)
```

Markers (declared in `pyproject.toml` `[tool.pytest.ini_options]`):

| Marker | Meaning |
|---|---|
| `unit` | Pure-logic tests. **No** I/O, no subprocess, no network. Must run in < 1s each. |
| `integration` | Touches the file system or subprocess via `tmp_path`. Network access is still banned. |
| `slow` | Anything > ~1s. CI runs these as a separate job. |

---

## Running

```powershell
# Inside the repo root, with the [test] extra installed:
pytest                              # everything (excluding `slow`)
pytest tests/unit -q                # unit only, quiet
pytest tests/unit/test_env_manager.py -k singleton
pytest -m "unit and not slow"
pytest --cov=xc_ce_utils --cov-report=term-missing
```

CI gate: **coverage ≥ 70%** for the `core_engine` package. Drops below the threshold fail the PR.

---

## Fixtures provided by `tests/conftest.py`

| Fixture | Purpose |
|---|---|
| `clean_env` | `pytest.MonkeyPatch` handle scoped to a single test, dedicated to env-var mutations. Use this (or `monkeypatch` directly) instead of touching `os.environ` so the change is rolled back automatically. |
| `minimal_project_conf` | A structurally valid one-level / one-variant `project_conf` dict. Use as a starting point for `VariantMatrix` and config-model tests. |
| `two_level_project_conf` | A two-level (platform/profile) matrix with multiple variants — exercises matrix expansion logic. |

### Optional-dependency stubs

`conftest.py` stubs the following modules so tests can import core-engine code **without** installing the `[core-engine]` extras:

```
requests, psutil, pandas, openpyxl, tabulate, git,
dng_helpers, conan, markdownify
```

Stubs are only enough to satisfy `import` statements. Any test that actually exercises code paths using the real library **must** install it (typically via a marker + a CI job that pulls the extra).

---

## Style rules

1. **Imports never run side-effects.** Module top-level must not open files, call subprocesses, or touch the network. Import-time crashes break the entire collection phase.
2. **Use `tmp_path`** for files, never the cwd or a fixed path.
3. **Use `monkeypatch` / `clean_env`** for env vars; do not assign to `os.environ`.
4. **Mock subprocess at the boundary.** When a unit under test calls `run_command`, patch `xc_ce_utils.global_modules.aux_helper.run_command` — not `subprocess.run` directly — so tests survive refactors of the helper.
5. **Reset singletons** in fixture teardown:
   - `EnvManager._reset_singleton_for_tests()`
   - `WrapperRegistry.reset()`
   - `StepRegistry.clear()` *(only in tests that rebuild the registry explicitly — most tests rely on auto-discovery)*
6. **One assertion concept per test.** Multiple `assert` statements are fine; multiple unrelated scenarios are not.
7. **Name tests descriptively.** `test_run_setup_skips_credential_phase_when_state_is_fresh` beats `test_run_setup_3`.

---

## Adding a new unit test

1. Find or create the matching `tests/unit/test_<module>.py`.
2. Import the symbol under test directly — do **not** import via `xc_ce_utils.<re-export>` shims unless explicitly testing that re-export.
3. Add a `pytestmark = pytest.mark.unit` at module top if all tests are unit (saves per-test markers).
4. Run `pytest tests/unit/test_<module>.py -q` locally before pushing.

### Template

```python
import pytest

pytestmark = pytest.mark.unit


def test_xyz_does_thing(clean_env, minimal_project_conf):
    clean_env.setenv("MY_FLAG", "1")
    # arrange, act, assert ...
```

---

## Adding a new integration test

1. Put it under `tests/integration/`.
2. Mark with `@pytest.mark.integration` (and `@pytest.mark.slow` if applicable).
3. Use `tmp_path` for any filesystem state.
4. If you need a subprocess, mock it unless the test is *specifically* asserting subprocess interaction.

---

## Stubbing third-party modules in a test (rare)

`conftest.py` already stubs the common offenders. If you need to stub something locally:

```python
import sys, types


def test_my_thing(monkeypatch):
    fake = types.ModuleType("some_pkg")
    fake.do_thing = lambda x: x + 1
    monkeypatch.setitem(sys.modules, "some_pkg", fake)
    # import the SUT after the stub is in place
    from my_module import use_some_pkg

    assert use_some_pkg(1) == 2
```

---

## CI behaviour

| Job | Runs |
|---|---|
| `unit-tests` | `pytest tests/unit -m "not slow"` |
| `integration-tests` | `pytest tests/integration` |
| `coverage` | `pytest --cov=xc_ce_utils --cov-report=xml`, uploaded to Codecov, threshold 70%. |

The PR gate is the union of unit + coverage. Integration is informational on PRs and required on `development`.

---

## Common pitfalls

- **`ImportError` only on Windows** — usually a forgotten stub for `pywin32`/`win32com`. Add the stub under `_OPTIONAL_STUBS` in `conftest.py`.
- **Test pollutes another test** — almost always env-var leakage; switch to `clean_env`.
- **`StepRegistry` already has 'my_step'** — running with auto-discovery + manual registration. Either rely on auto-discovery and don't re-register, or call `StepRegistry.clear()` at fixture setup.
- **`EnvManager` is sticky** — call `EnvManager._reset_singleton_for_tests()` in a fixture finalizer.
