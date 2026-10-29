# Build Tool Wrappers

The `core_engine/wrappers/` package provides Python wrappers around external build tools. Each wrapper standardizes invocation, logging, error handling, and path resolution.

```{note}
Conan support does **not** go through this wrapper package. The `conan_command` step
(`core_engine/steps/conan_steps.py`) invokes `uvx --from <spec> conan <args>` directly — there is
no `RBConanWrapper` or `ConanCacheManager` class. See [Conan / Package Management](steps/conan.md)
for the full step reference.
```

## RBCMakeWrapper

**File:** `wrappers/rb_cmake_wrapper.py`

Wraps CMake configure, build, test, and install operations.

Key features:

- **Preset support**: CMake presets (`--preset`) and traditional `-G` / `-D` workflows
- **Configure**: Sets generator, build type, install prefix, toolchain, custom defines
- **Build**: Target selection, parallel jobs, configuration
- **Test**: `ctest` execution with filtering and output options
- **Install**: `cmake --install` with prefix and component
- **ccache integration**: Optionally wraps compiler with ccache via `CMAKE_C_COMPILER_LAUNCHER`
- **Path resolution**: Auto-resolves source, build, and output directories from `ActionConfiguration`

## RBBazelWrapper

**File:** `wrappers/rb_bazel_wrapper.py`

Wraps Bazel build, test, run, query, and clean commands.

Key features:

- **Build**: `bazel build` with target patterns, platform flags, and remote cache configuration
- **Test**: `bazel test` with test filtering and output
- **Run**: `bazel run` for executable targets
- **Query**: `bazel query` for dependency analysis
- **Clean**: `bazel clean` with optional expunge
- **CI isolation**: Sets separate output directories in CI to avoid conflicts
- **Binary deployment**: `deploy_bazel_binaries()` — copies build outputs to the deployment folder

```{uml} ../../_diagrams/bazel_wrapper.puml
:caption: RBBazelWrapper interface and the bazel_steps.py step types that use it.
```

## RBMakeWrapper

**File:** `wrappers/rb_make_wrapper.py`

Wraps GNU Make.

Key features:

- **Build**: `make` with target, parallel jobs (`-j`), and custom variables
- **Clean**: `make clean` / `make distclean`
- **Install**: `make install` with prefix
- **Flags**: Passes `MAKEFLAGS` and arbitrary Make variables from config
- **Unified logging**: All Make output routed through `rb_logger`

## RBScriptRunner

**File:** `wrappers/rb_script_runner.py`

Executes external scripts (`.py`, `.ps1`, `.sh`, `.bat`, `.cmd`) as subprocesses.

Key features:

- **Argument conversion**: Converts config dict entries to CLI arguments (`--key value`)
- **Timeout**: Configurable subprocess timeout
- **Working directory**: Configurable `cwd`
- **Interpreter selection**: Auto-selects Python, PowerShell, Bash, or cmd based on file extension
- **Return code handling**: Raises on non-zero exit

## CcacheManager

**File:** `wrappers/ccache_utils.py`

Manages the ccache compiler cache.

Key features:

- **Detection**: Checks if ccache is available on the system
- **Statistics**: Retrieves cache hit/miss stats
- **Configuration**: Sets cache directory, max size, and other ccache options
- **Integration**: Used by `RBCMakeWrapper` when `--ccache` is enabled
