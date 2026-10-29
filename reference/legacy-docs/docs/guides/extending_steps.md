# Extending the Step Catalogue

This guide shows how to add a new **step type** to `xc-ce-utils` so it becomes addressable from any project's `build_conf.yml` via `type: my_new_step`. It assumes you have read the [Core Engine overview](../core_engine/index.md) and the [Step Reference](../core_engine/reference/step_reference.md).

---

## Decision tree â€” which base class?

| Your step wraps... | Use base class | Reason |
|---|---|---|
| A build tool already in `WrapperRegistry` (cmake, conan, bazel, make, script) | `WrappedStep` | Get free `WrapperRegistry.get(...)` integration so unit tests can swap fakes. |
| A new external tool with its own client / SDK | `ExecutionStep` (plain leaf) | You own the lifecycle directly. |
| A composite that orchestrates other steps | Already handled by `Set` nodes in YAML | You do **not** need a class â€” just write a `steps:` block. |

---

## 1. Choose a `step_type` name

Use lowercase snake_case (`<tool>_<verb>`), e.g. `mytool_flash`, `mytool_query`. Names must be globally unique across the registry â€” see `StepRegistry.available_types()` for the current list.

If your step fits an existing category (Build / Package Management / Quality & Analysis / Vendor / Deploy / Hardware / Network / File / Shell / Execution Control / Testing) add the name to `CATEGORY_MAP` in `core_engine/step_registry.py`; otherwise pass `category="..."` to the decorator.

---

## 2. Drop a `*_steps.py` file under `core_engine/steps/`

```python
# xc_ce_utils/core_engine/steps/mytool_steps.py
from typing import Any, Dict

from xc_ce_utils.core_engine.domain.exceptions import (
    ErrorRecoveryStrategy,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import ExecutionStep


@StepRegistry.register(
    "mytool_flash",
    category="Hardware",
    recovery=ErrorRecoveryStrategy.RETRY_ONCE,
)
class MyToolFlashStep(ExecutionStep):
    """Flash firmware via mytool-cli."""

    config_fields: Dict[str, Any] = {
        "device": {"required": True, "type": "str", "help": "Target device id"},
        "binary_path": {"required": True, "type": "path"},
        "verify": {"required": False, "type": "bool", "default": True},
    }
    env_vars: Dict[str, str] = {
        "MYTOOL_HOME": "Installation directory of mytool-cli",
    }

    def validate(self) -> None:
        super().validate()
        if not self.config["binary_path"].exists():
            raise ExecutionStepError(
                f"[{self.name}] binary_path does not exist: {self.config['binary_path']}"
            )

    def execute(self) -> None:
        # Do the work. Raising any exception terminates the step;
        # the engine wraps it as ExecutionStepError unless it is already one.
        self.context.run_command(
            [
                "mytool-cli",
                "flash",
                "--device",
                self.config["device"],
                str(self.config["binary_path"]),
            ],
            log_file=self.log_file_path,
        )
```

That is the entire registration. No edit to `core_engine/steps/__init__.py` is required â€” `_discover_step_modules()` auto-imports every `*_steps.py` file in the package on first access (works both as installed package and inside the PyInstaller bundle).

---

## 3. Pick an `ErrorRecoveryStrategy`

| Strategy | Effect |
|---|---|
| `ABORT` *(default)* | Step failure terminates the action immediately. |
| `CONTINUE_WITH_ERRORS` | Failure is logged, subsequent steps still run, the action exits non-zero at the end. |
| `RETRY_ONCE` | The step is re-executed once after a failure before applying the abort path. |
| `SKIP` | Failure is treated as success (use sparingly â€” currently appropriate for diagnostic-only steps). |

> Recovery is **declarative metadata** today. The execution engine still routes errors through the legacy `game_stopper` boolean + `AbortError` / `ContinueWithErrorsError` exceptions. Treat the strategy you set as the **target** behaviour â€” it becomes load-bearing once the engine adopts it (tracked in Phase 5 of the mega-refactor).

---

## 4. Wrap a build tool with `WrappedStep`

If your step calls `cmake`/`conan`/`bazel`/`make`/`script`, prefer `WrappedStep`:

```python
from xc_ce_utils.core_engine.steps.base import WrappedStep


@StepRegistry.register("cmake_my_target")
class CMakeMyTargetStep(WrappedStep):
    WRAPPER_NAME = "cmake"  # registry key in WrapperRegistry

    def execute(self) -> None:
        cmake = self.get_wrapper()  # -> rb_cmake_wrapper.RBCMakeWrapper
        cmake(build_dir=self.build_dir).build(targets=["my_target"])
```

Tests can then swap the wrapper without monkey-patching the import graph:

```python
from xc_ce_utils.core_engine.domain.wrapper_registry import WrapperRegistry


class FakeCMake: ...


WrapperRegistry.register("cmake", FakeCMake)
```

Use `WrapperRegistry.reset()` (or the `_reset_for_tests()` helper) in fixture teardown to restore the defaults.

---

## 5. Test it

Drop `tests/unit/test_mytool_step.py`:

```python
import pytest

from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.mytool_steps import MyToolFlashStep


def test_mytool_step_is_registered():
    assert StepRegistry.is_registered("mytool_flash")
    assert StepRegistry.get("mytool_flash") is MyToolFlashStep
    assert StepRegistry.get_category("mytool_flash") == "Hardware"


def test_mytool_step_validate_rejects_missing_binary(tmp_path):
    step = MyToolFlashStep(
        name="flash",
        config={"device": "tc377", "binary_path": tmp_path / "missing.bin"},
        context=None,
    )
    with pytest.raises(Exception):
        step.validate()
```

The auto-discovery in `core_engine/steps/__init__.py` will import the module the first time `StepRegistry` is used in the test session â€” no manual import needed in production code.

---

## 6. Use it in a project

```yaml
# any project's build_conf.yml
ACTIONS:
  flash:
    description: Flash firmware
    steps:
      flash:
        type: mytool_flash
        device: tc377
        binary_path: $BUILD_DIR/firmware.bin
        verify: true
```

The CLI auto-generates a `./build.ps1 flash` command.

---

## Cheat sheet

```{uml} ../_diagrams/step_lifecycle.puml
```

| Concern | Where it lives |
|---|---|
| Step class | `core_engine/steps/<name>_steps.py` |
| Registration | `@StepRegistry.register("name", category=..., recovery=...)` |
| Build-tool wrappers | `WrapperRegistry.get("cmake" | "conan" | "bazel" | "make" | "script")` |
| Auto-discovery | `core_engine/steps/__init__.py` â†’ `_discover_step_modules()` |
| Test fixtures | `tests/conftest.py` (`clean_env`, `minimal_project_conf`, `two_level_project_conf`) |
