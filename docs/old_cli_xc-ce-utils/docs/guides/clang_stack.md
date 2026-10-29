# Clang Tooling Stack

XC-CE Utils ships a complete clang-based developer tooling stack that
operates independently of the project's *real* embedded compiler
(Green Hills `cxtri`, TASKING `ctc`, IAR `iccarm`, Renesas, TI). The
stack gives every project the same IDE experience â€” formatting,
linting, jump-to-definition, hover types, refactoring, MISRA / CERT
diagnostics â€” without disturbing the firmware build.

This page is the single entry point for everything clang-related.
Each section links to the deep dives.

---

## Stack at a glance

| Layer                       | Tool                | Generated artefact                                | Owned by              |
| --------------------------- | ------------------- | ------------------------------------------------- | --------------------- |
| Compiler install            | clang via Chocolatey | `C:/tools/choco/lib/clang.*/tools/bin/`           | xc-ce-utils setup     |
| Formatting                  | `clang-format`      | `.clang-format` (per-tree)                        | layered base + overrides |
| Linting                     | `clang-tidy`        | `.clang-tidy` (per-directory)                     | layered base + overrides |
| IDE language server         | `clangd`            | `.clangd` + `compile_commands.json` symlink       | layered base + overrides |
| Parse-clean DB              | parallel CMake      | `_build/<variant>/<action>/clangd/compile_commands.json` | xc-ce-utils wrapper hook |
| Vendor extension support    | compat shim headers | `config/clang/compat/{greenhills,ifx,project}/*.h`| xc-ce-utils + project |
| MemMap noise suppression    | clang `-ivfsoverlay`| `_build/<variant>/<action>/clangd/clang_vfs/vfs.json`    | xc-ce-utils + project |

All of the above land in a consumer repo on the first
`xc-ce-utils` setup invocation; nothing needs to be installed
manually.

```{note}
`config/clang/...` above is the common **default** location, not guaranteed —
the actual config root is the parent directory of wherever `main_conf.yml`
resolves (overridable per project via `.xc-ce-utils`). See
[main_conf.yml's Discovery Order](config_files/main_conf.md#discovery-order).
```

---

## 1. clang installation (Chocolatey)

`EnvironmentSetup._install_clang_via_choco` ensures a pinned clang is
present on Windows runners and dev machines:

* Installs into `C:/tools/choco/lib/clang.<version>/tools/bin/`.
* The exact version is pinned by xc-ce-utils so every project sees
  the same `clang.exe`, `clangd.exe`, `clang-tidy.exe`,
  `clang-format.exe`.
* Linux uses the system clang resolved via `which clang`.
* Setup logs a one-line summary on every run; missing binaries fail
  setup early.

---

## 2. Layered configuration model

Every clang config file follows the **base + overrides + generated
root** pattern that the rest of the toolchain already uses for
`pre-commit` and `ruff` (see
[Code-Quality Config](code_quality_config.md)):

```text
<repo>/
â”œâ”€â”€ .clang-format                       # GENERATED â€” do not edit
â”œâ”€â”€ .clang-tidy                         # GENERATED â€” do not edit
â”œâ”€â”€ .clangd                             # GENERATED â€” do not edit
â””â”€â”€ config/clang/
    â”œâ”€â”€ clang_conf.yml                  # project knobs
    â”œâ”€â”€ clang-format/
    â”‚   â”œâ”€â”€ base                        # xc-ce-utils owned
    â”‚   â””â”€â”€ overrides                   # optional, project-owned
    â”œâ”€â”€ clang-tidy/
    â”‚   â”œâ”€â”€ base                        # xc-ce-utils owned
    â”‚   â””â”€â”€ overrides                   # optional, project-owned
    â”œâ”€â”€ clangd/
    â”‚   â”œâ”€â”€ base                        # xc-ce-utils owned
    â”‚   â””â”€â”€ overrides                   # optional, project-owned
    â””â”€â”€ compat/
        â”œâ”€â”€ greenhills/                 # xc-ce-utils owned
        â”œâ”€â”€ ifx/                        # xc-ce-utils owned
        â”œâ”€â”€ autosar/                    # reserved
        â””â”€â”€ project/                    # project-owned (never overwritten)
```

The merger (`xc_ce_utils/clang/config_layer.py`) regenerates the
three root files on every setup run, refuses to overwrite hand-edited
files without the `!!! GENERATED FILE` marker, and resolves the active
clang binaries through `clang/config_resolver.py`.

Authoritative defaults live in
[`xc_ce_utils/clang/templates/clang_conf.defaults.yml`](../../xc_ce_utils/clang/templates/clang_conf.defaults.yml).

---

## 3. `.clangd` â€” IDE language server

The generated `.clangd` pins the language server to:

* The xc-ce-utils-managed `clangd.exe` (no PATH guessing).
* A `CompilationDatabase` directory that points at
  `_build/compile_commands.json` â€” a stable symlink updated per
  variant by
  [`xc_ce_utils/clang/compile_commands.py`](../../xc_ce_utils/clang/compile_commands.py).
* `Index.Background: Build` for full project indexing.

VS Code picks this up automatically through the
[`vscode_integration`](../core_engine/reference/environment_setup_flow.md)
setup phase, which writes `.vscode/settings.json` with
`"clangd.path"` and `"clangd.arguments"` already aligned to the
shipped binary.

---

## 4. Parallel clangd CMake toolchain (PNG-style)

When the project's *real* compiler is not clang / GCC / MSVC, the
native `compile_commands.json` is full of vendor flags
(`-cpu=tc1v162`, `--gnu_asm`, `-list`, `-frigor=fast`, ...) that
clangd cannot parse. The stack solves this exactly the way
`png-gen1` does with GN: it runs a **second, configure-only** CMake
invocation against the same source tree using a generated clang
toolchain file. The two builds coexist:

```text
_build/<variant>/                  <- real Green Hills firmware build
  build/
    compile_commands.json          <- promoted clangd version
    compile_commands.native.json   <- original cxtri version (kept)
    xc_ce_definitions.cmake        <- variant defines, auto-generated
    clangd/                        <- parallel clangd configure (no link)
      xc_ce_clangd_toolchain.cmake <- generated by xc-ce-utils
      compile_commands.json        <- clang-readable database
      clang_vfs/                   <- optional MemMap VFS overlay
```

The hook fires from `RBCMakeWrapper.setup()` *after* the native
configure, is enabled per-project via
`clang_conf.yml::clangd_toolchain.enabled: auto|true|false`, and is
documented in detail in **[clangd_toolchain.md](clangd_toolchain.md)**
(target-triple selection, guard variable, compat shim injection,
per-variant defines).

Failures at any step degrade to warnings â€” the firmware build never
fails because of a clangd configuration issue.

---

## 5. Compatibility shim headers

The clang toolchain force-includes (`-include`) a curated set of
shim headers so clang accepts vendor extensions without project
changes:

```text
config/clang/compat/
  greenhills/   ghs-intrinsics-compat.h, ghs-attributes-compat.h, ghs-os-compat.h
  ifx/          ifx-mcal-compat.h
  autosar/      escrypt-hsm-compat.h
  project/      project-specific shims (never overwritten on regen)
```

Base shims under `greenhills/` and `ifx/` are owned by xc-ce-utils
and refreshed every run. Shims under `compat/project/` are appended
*after* the base shims, so a project shim wins when re-declaring
something. Typical project candidates: supplier BSW intrinsics
(Vector SIP, ETAS, EB tresos), CycurHSM / EVITA primitives, custom
AUTOSAR `MemMap.h` / `Compiler.h`.

---

## 6. MemMap VFS overlay

### What is a VFS overlay?

`-ivfsoverlay <vfs.json>` is a built-in clang feature that gives the
compiler a **virtual filesystem view**: at a real file path clang
reads alternative contents listed in a JSON manifest, while every
other tool (the real cxtri build, git, the editor) keeps seeing the
unchanged file on disk.

The JSON schema is fixed by clang:

```json
{
  "version": 0,
  "roots": [
    { "name": "<absolute dir>",
      "type": "directory",
      "contents": [
        { "name": "Mod_MemMap.h",
          "type": "file",
          "external-contents": "<absolute stub path>" }
      ] }
  ]
}
```

### What xc-ce-utils does

xc-ce-utils ports png-gen1's `mk-vfs.py` approach into
[`xc_ce_utils/clang/vfs_overlay.py`](../../xc_ce_utils/clang/vfs_overlay.py).
For every MemMap header listed in the project config it:

1. **Writes a stub** under
   `_build/<variant>/<action>/clangd/clang_vfs/stubs/<repo-relative-path>`
   containing only `#undef MEMMAP_ERROR` (matches PNG's
   `BUILD.gn` snippet 1:1, including the `{source}` comment for
   traceability). Writes are idempotent â€” unchanged stubs keep their
   mtime so Ninja does not re-trigger downstream invocations.2. **Emits `vfs.json`** under the same `clang_vfs/` directory,
   grouping sibling MemMap headers into one root entry (also matches
   PNG).
3. **Injects `-ivfsoverlay <vfs.json>`** into the generated parallel
   clangd toolchain (`xc_ce_clangd_toolchain.cmake`) so the
   configure-only CMake run automatically picks it up.

The real header on disk is **never** modified â€” only the virtual view
clang sees during indexing changes. The production firmware build
(Green Hills `cxtri`, TASKING `ctc`, ...) is unaffected.

### Enabling per-project

Add the patterns to `config/clang/clang_conf.yml`:

```yaml
enabled: true

clangd_toolchain:
  enabled: auto

  vfs:
    enabled: auto              # auto | true | false
    memmap_headers:
      - "SW/**/*_MemMap.h"     # globs are repo-root-relative
      - "src/bsw/**/MemMap.h"
    # Optional override of the stub body (default = "#undef MEMMAP_ERROR" only).
    # stub_lines:
    #   - "/* shadow of {source} */"
    #   - "#ifdef MEMMAP_ERROR"
    #   - "#undef MEMMAP_ERROR"
    #   - "#endif"
```

`auto` enables the overlay only when at least one header matches.
Explicit `true` with an empty `memmap_headers:` logs a warning and
skips the overlay; explicit `false` disables it unconditionally.
Failures during overlay generation are non-fatal â€” the parallel
clangd build continues without `-ivfsoverlay`, and the real firmware
build never sees them.

### Output layout

```text
_build/<variant>/<action>/clangd/clang_vfs/
    vfs.json                                    # overlay manifest
    stubs/SW/modA/ModA_MemMap.h                 # stub mirroring repo path
    stubs/SW/modB/ModB_MemMap.h                 # ...
```

---

## 7. Per-variant defines for clangd

The generated clangd toolchain `include()`s
`_build/<variant>/build/xc_ce_definitions.cmake` (auto-emitted by
`xc-ce-utils DefinitionsGenerator`). This propagates every
`BO_*` / `RB_*` variant define to the clangd build without parsing
`CMakeCache.txt` or duplicating the definitions list.

If the native build for the target variant has not run yet, the
generated toolchain emits a CMake warning and continues with
unconditional defines only.

---

## 8. Day-to-day developer workflow

```powershell
# First run after cloning â€” installs clang, deploys configs, generates
# .clang-format / .clang-tidy / .clangd, refreshes compile_commands.
.\build.ps1 --help

# Build a variant (also refreshes the clangd database for that variant).
.\build.ps1 -var pl9 build

# Switch variants â€” the compile_commands.json symlink is repointed
# automatically by the next setup pass.
.\build.ps1 -var pl7 build
```

No additional manual steps are needed for clangd, clang-tidy or
clang-format to "see" the active variant.

---

## 9. Source-of-truth pointers

| Concern                              | File                                                                 |
| ------------------------------------ | -------------------------------------------------------------------- |
| Clang install                        | `xc_ce_utils/core_engine/setup/phases/clang_phase.py`                |
| Layered config merger                | `xc_ce_utils/clang/config_layer.py`                                  |
| Config defaults                      | `xc_ce_utils/clang/templates/clang_conf.defaults.yml`                |
| Compiler family detection            | `xc_ce_utils/clang/compiler_detection.py`                            |
| Parallel clangd CMake configure       | `xc_ce_utils/clang/clangd_cmake_runner.py`                           |
| Wrapper hook                          | `xc_ce_utils/core_engine/wrappers/rb_cmake_wrapper.py` (`_maybe_configure_clangd_toolchain`) |
| `compile_commands.json` symlink mgmt  | `xc_ce_utils/clang/compile_commands.py`                              |
| Compat shim headers                   | `xc_ce_utils/clang/templates/compat/`                                |
| MemMap VFS overlay generator          | `xc_ce_utils/clang/vfs_overlay.py`                                   |
| Deep dive on the parallel toolchain   | [clangd_toolchain.md](clangd_toolchain.md)                           |
| Layered code-quality config           | [code_quality_config.md](code_quality_config.md)                     |

---

## 10. Troubleshooting

| Symptom                                                    | Likely cause / fix                                                                 |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| clangd shows `drv_unknown_argument` on every file          | `clangd_toolchain.enabled` is `false`/disabled â€” set to `auto`.                    |
| Jump-to-definition jumps to wrong variant                  | Run `.\build.ps1 -var <alias> --help` once to refresh the `compile_commands` link. |
| `sizeof(long) == 8` instead of `4` in hover                | `target_triple` not set â€” defaults to host MSVC triple; set to `i386-pc-windows-gnu` for TriCore. |
| Custom target `generate_elf_adx` errors during clangd configure | Guard it with `if(NOT XC_CE_CLANGD_TOOLCHAIN)` â€” see [clangd_toolchain.md](clangd_toolchain.md). |
| `#error "MEMMAP_ERROR"` shown in editor only               | Enable the VFS overlay: add globs to `clangd_toolchain.vfs.memmap_headers` (Section 6). |
| `.clang-tidy` not regenerated after edit                   | Check for the `!!! GENERATED FILE` marker â€” without it, the merger refuses to overwrite. |
