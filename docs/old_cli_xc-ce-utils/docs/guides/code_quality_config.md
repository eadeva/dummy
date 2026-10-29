# Code-Quality Config (pre-commit & ruff)

XC-CE Utils ships an opinionated, **layered** configuration for the two
code-quality tools every project uses on Python sources:

| Tool          | Generated root file        | Base (shipped)                                       | Overrides (project-owned, optional)     |
| ------------- | -------------------------- | ---------------------------------------------------- | --------------------------------------- |
| pre-commit    | `.pre-commit-config.yaml`  | `config/pre-commit/base.yaml`                        | `config/pre-commit/overrides.yaml`      |
| ruff          | `.ruff.toml`               | `config/ruff/base.toml`                              | `config/ruff/overrides.toml`            |

The goal is to keep the **XC-CE house style** in one place (the base files,
owned and updated by xc-ce-utils) while letting each project add its own
tweaks (the overrides). The two root files are **generated** and must not
be hand-edited.

```{note}
`config/` above is the common **default** config root, not guaranteed — the
actual root is the parent directory of wherever `main_conf.yml` resolves
(overridable per project via `.xc-ce-utils`). See [main_conf.yml's Discovery
Order](config_files/main_conf.md#discovery-order).
```

```{important}
The generator runs automatically on every `xc-ce-utils` setup invocation
(any non-`--help` command). There is nothing to install or wire up — the
files appear the first time you run the frozen exe in your repo.
```

---

## File layout in a consumer repo

After the first run you will find:

```text
<repo>/
├── .pre-commit-config.yaml        # GENERATED — do not edit
├── .ruff.toml                     # GENERATED — do not edit
└── config/
    ├── pre-commit/
    │   ├── base.yaml              # xc-ce-utils owned (auto-refreshed)
    │   ├── overrides.example.yaml # documentation of the 4 merge rules
    │   └── overrides.yaml         # OPTIONAL — your project tweaks
    └── ruff/
        ├── base.toml              # xc-ce-utils owned (auto-refreshed)
        ├── overrides.example.toml # documentation of the override mechanism
        └── overrides.toml         # OPTIONAL — your project tweaks
```

* `base.*` files are **overwritten** on every setup run — they are the
  upstream contract. Never edit them.
* `overrides.*` files are **created only by you** (or by your project lead
  during onboarding). xc-ce-utils never touches them.
* `.pre-commit-config.yaml` and `.ruff.toml` are regenerated only in
  maintainer setup paths (`config-devops hooks-setup` and
  `config-devops full-setup`) from base ± overrides.

---

## The safety net (`!!! GENERATED FILE`)

Every generated root file starts with this marker:

```yaml
# !!! GENERATED FILE -- DO NOT EDIT !!!
# Source: config/pre-commit/base.yaml + config/pre-commit/overrides.yaml (optional)
# Regen : runs during maintainer hooks setup (`config-devops hooks-setup`
#         or `config-devops full-setup`).
# Custom: edit config/pre-commit/overrides.yaml (see
#         xc_ce_utils/git_hooks/templates/pre-commit/overrides.example.yaml).
```

The deployer **refuses to overwrite** any existing root file that does
**not** start with that marker — instead it logs a migration hint. This
protects hand-edited legacy `.pre-commit-config.yaml` / `.ruff.toml` files
from being silently replaced. To migrate: delete (or `git rm`) the old
file and re-run setup; the generator will then own the root file.

---

## pre-commit — base + overrides

### Shipped base

`base.yaml` ships the XC-CE pre-commit baseline:

* `default_install_hook_types: [pre-commit, prepare-commit-msg, commit-msg]`
* The three xc-ce-utils **local hooks**: `xc-ce-task-id-prefix`,
  `xc-ce-commit-msg-format`, `xc-ce-branch-name` (invoked via the frozen
  xc-ce-utils binary — no separate Python/uv install required on dev
  machines).
* Hygiene/style hooks are explicitly staged to `pre-commit` only (so they
  do not run on `.git/COMMIT_EDITMSG` in `commit-msg`).
* A hygiene hook block from `pre-commit-hooks` v5.0.0 (trailing
  whitespace, EOF fixer, YAML/JSON/TOML linting, merge-conflict check,
  case-conflict check, mixed-line-ending with `--fix=auto`).
* reStructuredText hooks: `doc8` (`--ignore D004`) and `rstcheck`
  (`rstcheck[sphinx]`, `--report-level 2`, curated Sphinx-needs/custom
  extension directive ignores).
* Markdown hook: `pymarkdown` (`pymarkdown scan`) with relaxed style
  rules `MD013`, `MD034`, `MD036`, `MD041`; structural checks such as
  `MD040` and `MD042` remain active.
* `ruff --fix` and `ruff-format` (ruff 0.8.4).
* C/C++ hooks: `xc-ce-clang-format`, `xc-ce-clang-tidy`.
* Inventory entrypoint hook: `xc-ce-inventory-suite`
  (`inventory_check all`) with individually configurable sub-checks.

### Activatable checks in xc-ce-utils

The following checks are available in the shipped pre-commit baseline and
can be enabled/disabled or tuned via `config/pre-commit/overrides.yaml`
and/or `config/clang/clang_conf.yml`.

| Check / Hook ID | Stage | Default in base | Activation / tuning |
| --- | --- | --- | --- |
| `xc-ce-task-id-prefix` | `prepare-commit-msg` | enabled | Disable via `disable:` in `pre-commit/overrides.yaml` |
| `xc-ce-commit-msg-format` | `commit-msg` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `xc-ce-branch-name` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `trailing-whitespace` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `end-of-file-fixer` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `check-yaml` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `check-json` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `check-toml` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `doc8` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `rstcheck` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `pymarkdown` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `check-merge-conflict` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `check-case-conflict` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `mixed-line-ending` | `pre-commit` | enabled | Disable/override via `pre-commit/overrides.yaml` |
| `ruff` | `pre-commit` | enabled | Disable/override hook; tune with `config/ruff/overrides.toml` |
| `ruff-format` | `pre-commit` | enabled | Disable/override hook; tune with `config/ruff/overrides.toml` |
| `xc-ce-clang-format` | `pre-commit` | enabled | Requires `CLANG_CONFIG` + `enabled: true` |
| `xc-ce-clang-tidy` | `pre-commit` | enabled | Requires `CLANG_CONFIG` + `enabled: true`; compile DB required |
| `xc-ce-inventory-suite` | `pre-commit` | enabled | Runs `inventory_check all`; sub-check control is in `clang_conf.yml` |

Inventory sub-checks behind `xc-ce-inventory-suite` (individually
activatable in `config/clang/clang_conf.yml` under `precommit.inventory`):

| Sub-check | Default | Key controls |
| --- | --- | --- |
| `coverage` | enabled | `coverage.enabled`, `hard_fail`, `variant_scope`, `variants` |
| `metadata` | disabled | `metadata.enabled`, `hard_fail`, `applicability`, `manifest`, `schema` |
| `memmaps` | disabled | `memmaps.enabled`, `hard_fail`, `applicability`, `inventory_file`, `include_globs` |
| `tidy_threshold` | disabled | `tidy_threshold.enabled`, `hard_fail`, `variant_scope`, `variants`, `thresholds` |

`applicability` supports `auto | always | never` for `metadata` and
`memmaps`. In `auto`, the check runs only when the expected project
artifacts are present.

All third-party hooks run through `uvx --from <pkg>==<pin>` (sidecar
mode) so they share the developer's `uv` install and require no
language-runtime managed by pre-commit itself.

### Override mechanism (4 rules)

`config/pre-commit/overrides.yaml` is a partial YAML document that
expresses **deltas** against the base. The generator applies four
deterministic merge rules:

```yaml
# 1) TOP-LEVEL OVERRIDE — wins outright over the base value.
default_install_hook_types: [pre-commit]   # only run on commit
fail_fast: true

# 2) DISABLE — drop hooks (by id) from any repo.
disable:
  - xc-ce-task-id-prefix
  - xc-ce-commit-msg-format
  - xc-ce-branch-name

# 3) OVERRIDE — shallow-merge per-hook attributes (id is the join key).
override:
  - id: mixed-line-ending
    entry: uvx --from pre-commit-hooks==5.0.0 mixed-line-ending --fix=auto
  - id: trailing-whitespace
    exclude: '\.(patch|svg)$'

# 4) APPEND — additional repos. URL-keyed: repos with the same `repo:` URL
#    are merged (their `hooks:` lists are joined by id; `rev:` is bumped
#    forward when newer). Empty `repos:` blocks are dropped.
repos:
  - repo: https://github.com/codespell-project/codespell
    rev: v2.3.0
    hooks:
      - id: codespell
```

The merge rules are also enumerated in
`xc_ce_utils/git_hooks/templates/pre-commit/overrides.example.yaml`,
which is copied alongside `overrides.yaml` as a self-documenting
reference.

### Recognised top-level keys

The following root keys may be set in `overrides.yaml` and will win over
the base value:

```text
exclude
default_install_hook_types
default_language_version
default_stages
fail_fast
ci
minimum_pre_commit_version
```

Anything else is treated as one of the four structural rules above.

### Line endings: `.gitattributes` vs `mixed-line-ending`

Use this precedence model:

1. **Declare policy in `.gitattributes`** (canonical source of truth).
2. Keep `mixed-line-ending --fix=auto` as a pre-commit safety net.

`mixed-line-ending` normalizes staged text files before commit; Git then
applies `.gitattributes` checkout rules in each developer clone. They are
complementary, not conflicting, when policy is declared in attributes.

Example policies:

```ini
# LF-first (cross-platform / Linux-heavy)
* text=auto eol=lf
*.ps1 text eol=crlf
*.cmd text eol=crlf
*.bat text eol=crlf
```

```ini
# CRLF-first (Windows-heavy)
* text=auto eol=crlf
*.sh text eol=lf
*.bash text eol=lf
```

---

## ruff — base + overrides

### Shipped base (XC-CE Python style)

`config/ruff/base.toml` carries the XC-CE Python style stance:

| Setting | Value |
| --- | --- |
| `line-length` | 80 |
| `indent-width` | 4 |
| `cache-dir` | `.cache/ruff` |
| `[format]` | `quote-style = single`, `docstring-code-format = true` |
| `[lint] preview` | enabled |
| `[lint] select` | broad set incl. `A, ARG, B, C, C4, C90, CPY, E4, E7, E9, EM, F, FBT, FIX, FLY, I, N, NPY, PLC, PLE, PLR, PLW, RUF, SIM, SLF, TD, TID` |
| `[lint] ignore` | `B006, Q000, SIM115, PLW1514, UP015` (style stance, paired with `quote-style = single`) |

```{note}
The base intentionally **does not** set `exclude` / `extend-exclude`.
Ruff's built-in defaults already skip `.git`, `.venv`, `.ruff_cache`,
etc. Project-specific build directories (`_build`, `_bin`, `_log`,
`_reports`, `build`, `out`, …) belong in the per-repo overrides.
```

### Override mechanism (native ruff `extend`)

Ruff has native config-extension support, so no custom merger is needed.
The generated `.ruff.toml` is a one-liner that points at the right file:

* If `overrides.toml` exists →
  `extend = "config/ruff/overrides.toml"` (which in turn must start with
  `extend = "base.toml"`).
* If only `base.toml` exists →
  `extend = "config/ruff/base.toml"`.

A typical `overrides.toml` adds project-specific exclusions:

```toml
extend = "base.toml"

extend-exclude = [
    "_bin",
    "_build",
    "_log",
    "_reports",
]
```

Anything ruff supports is fair game — re-tighten an ignored rule, add
per-file rule sets, change line-length for the project, etc.

---

## Worked examples

### xc-ce-utils itself (`config/pre-commit/overrides.yaml`)

The xc-ce-utils repo is the meta-repo — it dogfoods the system but does
not want its own `xc-ce-*` local hooks running on its own commits:

```yaml
default_install_hook_types: [pre-commit]

disable:
  - xc-ce-task-id-prefix
  - xc-ce-commit-msg-format
  - xc-ce-branch-name

override:
  - id: mixed-line-ending
    entry: uvx --from pre-commit-hooks==5.0.0 mixed-line-ending --fix=auto
```

The local `xc-ce` repo block ends up with **zero** hooks after the
`disable:` rule runs; empty repos are dropped from the output.

### Example consumer project (`gw_2wp`)

`gw_2wp` is shown here as one concrete consumer-repo example. It uses
the shared ruff base and excludes build folders in
`config/ruff/overrides.toml`:

```toml
extend = "base.toml"

extend-exclude = ["_bin", "_build", "_log", "_reports"]
```

The same example project also uses `config/pre-commit/overrides.yaml` to disable
`xc-ce-commit-msg-format`.

### Example applicability profile (AUTOSAR-heavy consumer repo)

Using `gw_2wp` as a representative AUTOSAR-heavy consumer layout:

* `config/main_conf.yml` points to `CLANG_CONFIG: clang/clang_conf.yml`.
* `config/clang/clang_conf.yml` has `enabled: true`.
* `_build` contains `compile_commands.json` files.
* The tree contains many `*MemMap*.h` headers.
* No `config/clang/metadata*.json` file is present.

Example applicability matrix:

| Check | Example applicability | Recommendation |
| --- | --- | --- |
| Branch / task / commit-message checks | applicable | Keep enabled per project policy |
| Hygiene checks (`pre-commit-hooks`) | applicable | Keep enabled |
| `ruff`, `ruff-format` | applicable | Keep enabled for Python tooling/scripts |
| `xc-ce-clang-format` | applicable | Keep enabled |
| `xc-ce-clang-tidy` | applicable | Keep enabled; ensure compile DB is refreshed for active variants |
| Inventory `coverage` | applicable | Enable hard-fail only after team baseline review |
| Inventory `metadata` | conditionally applicable | Keep disabled (or `applicability: auto`) until metadata manifest/schema is introduced |
| Inventory `memmaps` | strongly applicable | Enable for AUTOSAR-heavy trees; `applicability: auto` is suitable |
| Inventory `tidy_threshold` | applicable | Introduce gradually with curated thresholds per diagnostic |

```{note}
If a consumer repo pins an older `XC_CE_UTILS_VERSION` and its deployed
`config/pre-commit/base.yaml` does not yet contain `xc-ce-inventory-suite`,
update xc-ce-utils to a version that includes the inventory suite baseline,
then rerun setup to refresh generated pre-commit files.
```

---

## Migrating an existing project

1. Run any `xc-ce-utils` command in the repo (e.g. `xc-ce-utils.exe
   config`). The git-hooks phase will fire.
2. If you already have a hand-edited `.pre-commit-config.yaml` or
   `.ruff.toml`, the deployer **skips** that root file and logs a hint.
   Inspect the file, move any project-specific bits into the new
   `config/<tool>/overrides.*`, then `git rm` the old root file.
3. Re-run the command. The generator now owns the root file and writes
   the `!!! GENERATED FILE` marker.
4. Commit the deployed `config/<tool>/base.*`, your `overrides.*`, and
   the regenerated root files together.

````{tip}
Validate the resolved ruff config without running checks:

```powershell
uvx --from ruff==0.8.4 ruff check --show-settings | Select-String 'line_length|quote_style|extend_exclude'
```
````

---

## Reference

* Implementation: `xc_ce_utils/git_hooks/config_layer.py`
  (`deploy_code_quality_configs`, `_merge_pre_commit`, `_safe_write_generated`).
* Shipped templates:
  `xc_ce_utils/git_hooks/templates/pre-commit/*`,
  `xc_ce_utils/git_hooks/templates/ruff/*`.
* Setup integration: `GitHooksPhase` in
  `xc_ce_utils/core_engine/setup/phases/git_hooks_phase.py`.
* Tests: `tests/unit/test_config_layer.py` (19 unit tests covering the
  four merge rules, the safety-net behaviour, and end-to-end
  deployment).
