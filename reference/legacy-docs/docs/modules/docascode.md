# Docs as Code

**Package:** `xc_ce_utils.docascode`

Documentation-as-Code generation via Sphinx, sphinx-needs 8, Doxygen, and PlantUML.

---

## Purpose

Automates project documentation builds using industry-standard tools. Coordinates Sphinx (MyST-markdown / reStructuredText), sphinx-needs (requirements, architecture and test traceability), Doxygen (C/C++ API), and PlantUML (diagrams) into a single documentation pipeline. The sphinx-needs configuration is generated from the PMT docs-as-code meta model, architecture needs from `*.arch.yml` models, and test cases and verdicts are connected to [TACO](../core_engine/reference/steps/taco.md).

---

## Key Components

### `generate_docs.py`

Main orchestrator for documentation generation.

```python
from xc_ce_utils.docascode.generate_docs import generate_documentation

generate_documentation(repo_root=".", build_folder="_build/docs", fail_on_warning=True)
```

Supports Sphinx builder selection and needs export filtering:

```python
generate_documentation(
    build_folder="_build/docs",
    reports_folder="_build/docs/needs",
    builder="needs",
    exclude_directives=["mm-class", "req-sw"],
)
```

- `builder="needs"` generates `needs.json` without running Doxygen; Java and PlantUML are not required (see [Needs-only builds](#needs-only-builds)).
- `exclude_directives` is optional and removes matching need `type` entries from generated `needs.json`.

### `blockdiagramsync.py`

Synchronises PlantUML `.puml` files to folder structures — keeps rendered diagrams in sync with source.

### `conf_standard.py`

Provides a standard Sphinx `conf.py` configuration with automatic extension loading (`sphinxcontrib.plantuml`, `sphinx_needs`, `breathe`, `myst_parser`, `sphinx_design`, `sphinx.ext.ifconfig` and the extensions below). Projects import it from their own `conf.py`.

### Sphinx extensions

| Extension | Purpose |
|---|---|
| `needs_yaml_loader` | Builds the sphinx-needs configuration: generated meta-model layer + `needs_config.yml` layers (see below) |
| `meta_model` | `meta_model_docu` / `meta_model_puml` directives documenting the meta model |
| `meta_model_validation` | Post-build report of needs violating the meta model (mandatory attributes, values, relations, lifecycle) |
| `archuml` / `functree` | PlantUML component diagrams and function trees from architecture needs |
| `taco_catalog` | Generates the TACO test catalog (RST) from the test sources (`taco_tc_*` in `conf.py`) |
| `yaml_rst_parser` | `include-yaml-rst` directive: renders the `test-plan` / `test-suite` needs of TACO `.tl.yaml` / `.ts.yaml` files |
| `verdict_overlay` | Writes TACO verdicts and report URLs onto the test case needs (`TACO_RESULTS_DIR`) |
| `ssl_inheritance` | Test cases inherit `safety` / `security` / `legal` from the needs they validate (most conservative value wins) |
| `variant_handling` | Variant of the build in the sources: config values, tag, variant files, sphinx-needs variant data (see [Variant handling](#variant-handling)) |

### `generate_needs.py` and `pmt_meta_model/`

- `generate_needs.py` (Arch2Needs) generates the architecture needs from the `*.arch.yml` models, see [Architecture needs](#architecture-needs-arch2needs).
- `pmt_meta_model/model_to_needs.py` turns the PMT meta model into the sphinx-needs configuration and the `mm-*` meta-model needs.
- `pmt_meta_model/meta_model_project_overrides.py` applies the project deviations to the meta model.

---

## Sphinx-Needs Configuration and the PMT Meta Model

The `needs_yaml_loader` extension builds the sphinx-needs 8 configuration on every build:

1. load the PMT meta model (`pmt_meta_model/meta_model_spec.yaml`),
2. apply the project deviations (`meta_model_deviations.yaml`, see below),
3. generate `needs_types`, `needs_fields`, `needs_links` and the per-type
   `needs_schema_definitions` from the result,
4. merge the xc-ce-utils `needs_config.yml` and the project `needs_config.yml` (next to
   `conf.py`) on top.

Both `needs_config.yml` layers only hold what the meta model cannot express: core settings,
defaults/predicates, string links, layouts, the `mm-*` infrastructure, the type-independent
field `used_in_image`, and `allow_dead_links` on meta-model links. Types, attributes and
relations missing in the meta model are deviations. Redefining a meta-model type, the values or
the obligation of a meta-model field, or a meta-model link fails the build with a pointer to
`meta_model_deviations.yaml`. The former `merge_ops` and the YAML constraints
(`needs_constraints`, `extra_constraints`, `needs_constraint_failed_options`) are no longer
supported; validation runs through the generated `needs_schema_definitions`.

The log folder receives `needs_config.generated.yml` (generated layer incl. the applied
deviations), `needs_config_merged.yml` and `needs_yaml_merge_report.log`.

### Project Deviations from the Meta Model

`meta_model_spec.yaml` is replaced with every PMT update, so projects do not edit it. Deviations
are recorded in `meta_model_deviations.yaml` (same format as the PMT `apply_meta_model_deviations`)
and applied to the meta model before anything is generated, so they reach the configuration, the
meta-model needs and `meta_model_validation` through one path.

The file is taken from the `docascode` step parameter `meta_model_deviations` (environment
variable `META_MODEL_DEVIATIONS`), else from `meta_model_deviations.yaml` next to `conf.py`.
Without either, the meta model is used unchanged.

```yaml
schema_version: 1
deviations:
  - id: DEV_0001
    target: ATTR_TC_SwC_test_tool
    operation: extend_values
    values: [MyProjectTestTool]
    rationale: >
      Component tests use the project-owned harness MyProjectTestTool, which the standard value
      list does not cover.
```

Every deviation needs a unique `DEV_` ID and a rationale.

| Operation | Target | Effect |
|---|---|---|
| `extend_values` | `mm-attribute` | add allowed values |
| `remove_values` | `mm-attribute` | drop allowed values (at least one remains) |
| `set_mandatory` | `mm-attribute` | relax to optional or tighten to mandatory |
| `set_cardinality` | `mm-relation` | change the cardinality, e.g. `0..*` |
| `extend_target_classes` | `mm-relation` | let the relation point at additional classes |
| `add_object` | `mm-class`, optional | add an attribute/relation below a class, or (without `target`) a new top-level class with `section` and `children` |
| `set_values` (xc) | `mm-attribute` | replace the value list, or `str` for free text |
| `set_lifecycle` (xc) | any | change `lifecycle_status` |
| `remove_object` (xc) | any | remove an object with its children |

The operations marked (xc) and glob targets are xc-ce-utils additions to the PMT format. A glob
target such as `ATTR_*_safety` applies the deviation to every matching object; matches the
deviation would leave unchanged (and free-text attributes) are skipped, at least one has to change.

The build stops if a deviation, among other things, has a malformed or duplicate ID, misses the
rationale, targets an unknown, wrongly typed or retired object, leaves its target unchanged, adds
a value that is already allowed or removes one that is not, removes every value, or adds an object
whose ID does not match its position. One run reports every faulty deviation.

**Traceability.** No new need type, field, link or directive is introduced. A deviation leaves two
traces on the meta-model needs:

- every changed or added object is tagged `deviation` plus the deviation ID;
- the rationale is appended to the object's description as
  `**Project deviation <ID>** (<operation>): …` (for an added class once, on the class).

The deviated meta-model needs are registered as `needimport` key `meta_model`. Import them on the
page documenting the meta model and list the deviations with a plain `needtable`:

```rst
.. needimport:: meta_model

.. needtable:: Objects deviating from the standard meta model
   :filter: "deviation" in tags
   :columns: id, type, title, tags
```

`meta_model_docu` marks deviated attributes, relations and child classes with the responsible
deviation ID, and `meta_model_validation` validates against the deviated model.

---

## Architecture Needs (Arch2Needs)

The architecture (building blocks, interfaces, function trees) is modelled in `*.arch.yml` files
and converted into needs before Sphinx reads the sources. The project `conf.py` runs the
`generate_sphinx_needs` pre-build step (`docascode` parameter `pre_build_steps`) with a
configuration such as:

```yaml
catalogs: [docs/ref_arch/ref_arch.json, docs/ref_arch/features.json]  # optional
arch_dirs: [docs]                       # all *.arch.yml below (folders _* and .* skipped)
output_dir: docs/_gen_needs
reuse_map: {file: ..., sheet: ...}      # optional: marks needed features as used
box_in_box: {url: ..., templates: [...]}  # optional: box-in-box draw.io views
allow_warnings: true
allow_errors: false                     # true continues on model errors
```

The generated needs are checked against the merged sphinx-needs configuration (need types, ID
prefixes, values and link targets); the findings are written to `architecture_validation.log`
in the action log folder. Arch2Needs writes `sys-feature`, `hw-function` and `hw-element`, which
the PMT meta model does not define (it has `feature`, `sys-function` with `domain: HW` and
`sys-techelm`); projects using them declare them as deviations.

With a variant (see [Variant Handling](#variant-handling)), `<name>.<alias>.arch.yml` files are
only loaded for that variant, the files without a variant for all variants (a build without
variant loads only those). The outputs get the variant in their names, so the outputs of all
variants exist side by side: `gen_needs.<alias>.rst` imports `<project>_<type>_needs.<alias>.json`.
The `gen_needs.<other alias>.rst` files are excluded, so include the page with a `:glob:`
toctree entry `_gen_needs/gen_needs*`. A variant build deletes the outputs of a build without
variant (`gen_needs.rst`, `<project>_<type>_needs.json`), which would duplicate the needs.

---

## TACO Integration

The documentation is the source of TACO's test cases and shows their results:

1. `taco_catalog` turns the test cases embedded in the test sources (GoogleTest, Robot
   Framework) into needs; `include-yaml-rst` documents the TACO test plans and suites.
2. A `docascode` step with `builder: needs` produces the `needs.json` the
   [TACO steps](../core_engine/reference/steps/taco.md) select from.
3. The TACO steps collect their result JSONs in `_reports/<variant>/taco_results`.
4. The `doc` action's `taco_results_dir` points `verdict_overlay` at that folder, which writes
   `latest_test_verdict` and `latest_report_path` onto the test cases; `ssl_inheritance` fills
   their `safety` / `security` / `legal` from the validated needs.

Test plans and suites per variant: `<name>.<alias>.tl.yaml` / `<name>.<alias>.ts.yaml` next to
`<name>.tl.yaml` / `<name>.ts.yaml` replaces it for that variant, in the TACO steps
(`test_list`) and in `include-yaml-rst`; without a variant file the common file is used. TACO
reads all `*.ts.yaml` of the suite folder, so the suites of different variants need different
suite IDs (selected by the variant's `.tl.yaml`). The test case catalog (`taco_catalog`) is
generated from the test sources and lists all test cases.

---

## Needs-only Builds

`builder: needs` reads the sources and writes `needs.json` only. It skips Doxygen, and it does
not need Java or PlantUML: diagrams are rendered by the HTML writer only. A missing PlantUML jar
or Java is therefore just a warning for the needs builder (an error for all other builders), so
CI jobs that only need `needs.json` (e.g. before TACO test selections) do not need these tools.
The builder is passed to `conf.py` as `XC_CE_UTILS_DOCS_BUILDER`, so a project `conf.py` can
relax its own PlantUML checks the same way.

---

## Variant Handling

The documentation is built per variant (`build.ps1 -var <variant> doc`). The `docascode` step
passes the variant to Sphinx (`XC_CE_UTILS_VARIANT_ALIAS`, `XC_CE_UTILS_VARIANT_CONFIG` with the
variant configuration as JSON, `XC_CE_UTILS_VARIANT_ALIASES` with all variant aliases) and the
`variant_handling` extension makes it available to the sources:

| Provided | Value (example `cgw_plus`) | Use |
|---|---|---|
| config value `variant` | `'cgw_plus'` | `.. ifconfig:: variant == 'cgw_plus'` |
| config value `variant_config` | dict of the variant (`alias`, `description`, `version`, ... and project keys) | `.. ifconfig:: variant_config.get('version') == 'v2.*'` |
| config value `variant_aliases` | `['cgw_cs', 'cgw_plus']` | |
| tag | `cgw_plus` | `.. only:: cgw_plus` |
| substitution | `\|variant\|` (RST), `{{variant}}` (MyST) | text |
| `needs_variant_data` | `var.variant`, `var.variant_config.*` | `.. if::`, need filters, `needs_variants` |
| `needs_variants` | one entry per alias: `var.variant == '<alias>'` | variant values of need fields |
| `exclude_patterns` | files `<name>.<other alias>.rst` / `.md` | whole pages per variant |

Which one to use:

- **Whole pages of a variant:** name them `<name>.<alias>.rst` (or `.md`). The files of the
  other variants are excluded, so their needs and table-of-contents entries do not exist in this
  variant. Without a variant (local build without `-var`) all variant files are excluded. Include
  them with a `:glob:` toctree so the missing pages of the other variants do not warn.
- **Content with needs:** sphinx-needs `.. if::`. Its content is only read when the expression
  is true, so the needs inside are not registered for the other variants:

  ```rst
  .. if:: var.variant == 'cgw_plus'

     .. req-sw:: Only in CGW Plus
        :id: REQ_Sw_Plus_001
  ```

- **Text without needs:** `.. only:: cgw_plus`, or `.. ifconfig::` for conditions on
  `variant_config`.
- **Need field values per variant:** enable `parse_variants: true` for the field in
  `needs_fields` (`needs_config.yml`), then `:status: <<cgw_plus:open, closed>>` (the last value
  without expression is the default).
- **Tables and flows of one variant:** filter on the variant data, e.g.
  `:filter: var.variant == 'cgw_plus' and type == 'req-sw'`.
- **Architecture models:** `<name>.<alias>.arch.yml`, see
  [Architecture Needs](#architecture-needs-arch2needs).
- **TACO test plans / suites:** `<name>.<alias>.tl.yaml` / `.ts.yaml`, see
  [TACO Integration](#taco-integration).

> Do not put needs inside `.. only::` or `.. ifconfig::`: sphinx-needs registers them while
> reading, before these directives remove their content, so the needs would still appear in
> needtables, flows and the traceability of every variant. Use `.. if::` or variant files.

The project `conf.py` can override all values (`variant`, `variant_config`, `variant_aliases`,
`needs_variant_data` and `needs_variants` keys); `needs_filter_data` (deprecated since
sphinx-needs 8.2) is not used.

---

## Tool Installation

PlantUML, Doxygen, and Graphviz are installed automatically via Toolbase when running the documentation build phase. Needs-only builds (`builder: needs`) do not need them.

---

## Step Type

| Step Type | Description |
|---|---|
| `docascode` | Generate project documentation |

---

## Build System Usage

```bash
# Generate documentation
./build.ps1 -var <variant> doc

# Generate needs.json only via dedicated action
./build.ps1 -var <variant> splunk-dac

# Configuration in:
# config/docascode/sphinx/    — Sphinx settings
# config/docascode/doxygen/   — Doxyfile
# config/docascode/plantuml/  — PlantUML includes
```

```{note}
`config/docascode/` above is the common **default** location, not
guaranteed — the actual config root is the parent directory of wherever
`main_conf.yml` resolves (overridable per project via `.xc-ce-utils`). See
[main_conf.yml's Discovery Order](../guides/config_files/main_conf.md#discovery-order).
```

Action example (`config/actions/splunk_export_needs.yml`):

```yaml
PHASES:
  needs_gen:
    step_type: docascode
    builder: needs
    exclude_directives: []
```

---

## See Also

- [Execution Engine](../core_engine/05_building_block_view.md) — build orchestration
- [`docascode` step](../core_engine/reference/steps/quality.md) — step parameters
- [TACO steps](../core_engine/reference/steps/taco.md) — test selections and verdicts
