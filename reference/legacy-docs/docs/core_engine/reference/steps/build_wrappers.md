# Build Wrappers (CMake / Make / Bazel)

All steps in this category are `WrappedStep` subclasses; they obtain their wrapper from the engine via `self.get_wrapper()`.

## `cmake_set-up`

- **Source:** [`cmake_steps.py`](../../../../xc_ce_utils/core_engine/steps/cmake_steps.py)
- **Base / wrapper:** `WrappedStep` / `cmake` (`RBCMakeWrapper`)
- **Behavior:** Deletes `CMakeCache.txt` and `bin_folder` for a clean configure. If `context.ccache` + `context.ccache_dir` are set, primes ccache via `setup_ccache_environment`. Without `preset` runs `cmake_wrapper.setup(cmake_args)`; with `preset` runs `cmake_wrapper.run_preset(preset, "build", extra_args=cmake_args)`. Native mode generates `xc_ce_definitions.cmake` via `DefinitionsGenerator` and passes it as `-DCMAKE_PROJECT_INCLUDE`; Conan mode points `-DCMAKE_TOOLCHAIN_FILE` at `{build_folder}/conan_install/conan_toolchain.cmake`.

| Key | Type | Description |
|---|---|---|
| `preset` | str | If set, drives a CMake preset instead of a raw configure. |
| `cmake_args` | list[str] | Extra args appended to the configure command. |
| `toolchain_file` | str | Explicit `-DCMAKE_TOOLCHAIN_FILE=...`. |
| `conan_toolchain` | bool | Use Conan-generated toolchain (skip native definitions). |

```yaml
configure:
  type: cmake_set-up
  preset: ninja-release
  cmake_args: ["-DENABLE_LTO=ON"]
```

## `cmake_build`

- **Source:** [`cmake_steps.py`](../../../../xc_ce_utils/core_engine/steps/cmake_steps.py)
- **Base / wrapper:** `WrappedStep` / `cmake`
- **Behavior:** Reads `use_ccache`/`ccache_dir` from the variant's build options. Builds via preset or default. In `dev_mode` / `single_file` mode runs the empty-line remover on `.i` files and stages them under `_reports/.../devmode/`. Single-file mode forces target `compile_single_file`.

```yaml
build:
  type: cmake_build
  preset: ninja-release
```

## `ctest`

- **Source:** [`cmake_steps.py`](../../../../xc_ce_utils/core_engine/steps/cmake_steps.py)
- **Base / wrapper:** `WrappedStep` / `cmake`
- **Behavior:** Runs the `test` step of preset `build_conf["PRESET"]`. Reuses `context.cmake_wrapper` if available; otherwise instantiates one bound to `_build/{variant_path}/{action}`.

```yaml
unit_tests:
  type: ctest
```

## `make`

- **Source:** [`make_steps.py`](../../../../xc_ce_utils/core_engine/steps/make_steps.py)
- **Base / wrapper:** `WrappedStep` / `make`
- **Behavior:** Caches `context.make_wrapper`. Generates native definitions via `DefinitionsGenerator.write_make(...)` unless `conan_toolchain` is true. Runs `make_wrapper.build(target, variables=...)`.

```yaml
build:
  type: make
  target: all
  variables:
    DEBUG: "1"
  conan_toolchain: false
```

## `make_clean`

- **Source:** [`make_steps.py`](../../../../xc_ce_utils/core_engine/steps/make_steps.py)
- **Base / wrapper:** `WrappedStep` / `make`
- **Behavior:** Caches `context.make_wrapper` and runs `make_wrapper.clean()`.

```yaml
clean:
  type: make_clean
```

## `bazel_build`

- **Source:** [`bazel_steps.py`](../../../../xc_ce_utils/core_engine/steps/bazel_steps.py)
- **Base / wrapper:** `WrappedStep` / `bazel` (`RBBazelWrapper`)
- **Behavior:** Generates native definitions (`gen.write_bazel(...)`) unless `conan_toolchain` is true. Maps `context.build_type` to `compilation_mode` (`Debug` → `dbg`, `Release` / `MinSizeRel` → `opt`, `RelWithDebInfo` → `fastbuild`). Passes `clean=context.rebuild` so `--expunge` runs before building. Honors `context.no_cache`.

```yaml
build:
  type: bazel_build
  target: //app:firmware
  deploy_binaries: true
  args: ["--copt=-O2"]
```

## `bazel_test`

```yaml
test:
  type: bazel_test
  target: //test/...
  test_output: errors
```

## `bazel_run`

```yaml
run_tool:
  type: bazel_run
  target: //tools:code_gen
  args: ["--out=generated/"]
```

## `bazel_clean`

```yaml
clean:
  type: bazel_clean
  expunge: true
```

## `bazel_query`

```yaml
list_targets:
  type: bazel_query
  query_expression: "kind('cc_binary', //...)"
  output_format: label
```

## Category index

| Step type | Description |
|---|---|
| `cmake_set-up` | CMake configure (presets or traditional) |
| `cmake_build` | CMake build |
| `ctest` | CMake test execution |
| `make` | GNU Make build |
| `make_clean` | GNU Make clean |
| `bazel_build` | Bazel build |
| `bazel_test` | Bazel test |
| `bazel_run` | Bazel run |
| `bazel_clean` | Bazel clean |
| `bazel_query` | Bazel query |
