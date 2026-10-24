# ptk — project tool kit

A configuration-driven project CLI: actions made of steps and step sets,
built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting. See [`docs/PLAN.md`](docs/PLAN.md) for the full plan.

**Status:** M1 (configuration meta-model and loader) and M2 (variant core) are done.

```bash
uv sync                     # install with dev dependencies
uv run ptk --help
uv run pytest
```

## Configuration files

All ptk files end in `.ptk.yml`:

| File | Purpose |
|------|---------|
| `main.ptk.yml` | entry point: `ptk_version`, project, includes, main settings |
| `*.ptk.yml` | fragments pulled in with `include:` (e.g. `ptk/actions/*.ptk.yml`) |
| `ci.ptk.yml` | applied automatically in CI |
| `local.ptk.yml` | personal overrides (git-ignore it) |
| `maintainers.ptk.yml` | who sees maintainer-only actions |

```yaml
# main.ptk.yml
schema_version: 1
ptk_version: ">=0.1,<0.2"          # ptk refuses to run with another version
project: {name: demo, default_action: build}
include: [ptk/actions/*.ptk.yml]
variants: ptk/variants.ptk.yml       # plain string = include this file here
vars: {preset: "${vh.variant}"}
```

Loading order: `main.ptk.yml` (+ includes) → `ci.ptk.yml` (in CI) →
`local.ptk.yml` → `--set PATH=VALUE`.

* mappings merge deeply, lists are replaced; `!replace`, `!append` and
  `!include file-or-glob` give explicit control
* every value remembers its file and line: `ptk config show --sources`
* unknown keys, unknown names in conditions and `${...}` references are errors
  with `file:line` and "did you mean ..."
* `ptk config schema -o .ptk/schema.json` for editor autocompletion

## Commands available now

```
ptk [-c main.ptk.yml] [--set PATH=VALUE]... [--ci/--no-ci]
ptk config validate | show [PATH] [--sources] [--format yaml|json] | schema [-o FILE]
ptk variant list [--names] | show [NAME] [--json] [--all] | explain NAME FEATURE | check [NAMES] [--strict]
```

## Workspace layout

```
_builds/<variant>/<action>/<set>/<step>/    working directory per step
_bin/<variant>/                             binaries per variant
_logs/<variant>/<action>/run.log            + <set>/<step>.log
_reports/<variant>/<action>/<set>/<step>/
```

## Architecture

```
src/ptk/
  domain/        config meta-model, tree + merge rules, substitution, expressions,
                 variants (model, rules, conventions), layout
  application/   ports, use cases (LoadProject, ShowConfig, ExportSchema, VariantService)
  adapters/      YAML loader (includes, tags, provenance), file source, host environment
  drivers/cli/   rich_click CLI
  bootstrap.py   composition root
```

Dependencies point inwards only; the domain has no I/O.
