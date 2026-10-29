# Quality & Analysis

Documentation generation, OSS scans, and Helix QAC integrations.

## `docascode`

- **Source:** [`quality_steps.py`](../../../../xc_ce_utils/core_engine/steps/quality_steps.py)
- **Behavior:** Lazy-imports `xc_ce_utils.docascode.generate_docs.generate_documentation(...)`.
- **Output:**
  - `builder: html` (default) writes to `{build_folder}/html`
  - `builder: needs` writes to `{build_folder}/needs` (`needs.json` only; no Doxygen, and Java/PlantUML are not required)
- **Options:**
  - `allow_warnings` (bool, optional): if `true`, Sphinx warnings do not fail the step.
  - `builder` (str, optional): Sphinx builder name, typically `html` or `needs`.
  - `docascode_config_folder` (str, optional): folder with the project's `sphinx/conf.py` (and `doxygen/`), relative to the repository root.
  - `exclude_directives` (list[str], optional): with `builder: needs`, removes needs entries by `type` from generated `needs.json`.
  - `pre_build_steps` (list, optional): generators run by the project `conf.py` before Sphinx reads the sources, e.g. `generate_sphinx_needs` (architecture needs from `*.arch.yml`, with `config:` pointing to the Arch2Needs configuration) and `process_visio_svgs`. Each entry has `name`, `enabled` and step-specific keys.
  - `taco_results_dir` (str, optional): folder with TACO result JSONs, relative to the repository root (sets `TACO_RESULTS_DIR`); their verdicts are shown on the test cases. See [TACO](taco.md).
  - `meta_model_deviations` (str, optional): project deviations from the PMT meta model, relative to the repository root (sets `META_MODEL_DEVIATIONS`). Without it, `meta_model_deviations.yaml` next to `conf.py` is used if present. See [Docs as Code](../../../modules/docascode.md#project-deviations-from-the-meta-model).
  - `open_docs` (bool, optional, default `false`): with `builder: html`, opens the generated `index.html` in the default browser after a successful build. Ignored in CI; with another builder it only logs a warning.

```yaml
docs:
  type: docascode
  allow_warnings: false
  open_docs: true
  docascode_config_folder: build_environment/xc-ce-utils/docascode
  pre_build_steps:
    - name: generate_sphinx_needs
      enabled: true
      config: build_environment/xc-ce-utils/docascode/sphinx/arch2needs_conf.yml
  taco_results_dir: $ENV{XC_CE_UTILS_REPORTS_DIR}/$ENV{XC_CE_UTILS_VARIANT_ALIAS}/taco_results

needs_export:
  type: docascode
  builder: needs
  exclude_directives:
    - mm-class
    - req-sw
```

## `oss`

- **CI-only.**
- **Behavior:** Extracts sources via `oss.sw_source_extractor.extract_sources`, then runs FOSSID via `oss.fossid_script_api.create_and_run_scan`. Requires `context.oss_config`.

```yaml
fossid_scan:
  type: oss
```

## `qac`

- **Behavior:** Calls `xc_ce_utils.helix_qac.run_static_code_analysis(...)` directly from the `xc-ce-utils` runtime (no dedicated `xc-ce_helix-qac` executable). `create_baseline` defaults to `is_running_in_ci()`. Hardcodes `--source_branch development`. Auto-passes `--build_folder`, `--logs_folder`, `--reports_folder`.
- **Baseline path parameter:** `baseline_repository_full_path` is mandatory when `sfa: true` or `create_baseline: true`. It defines the full repository path (inside the configured Artifactory repository) for baseline download/upload.
- **Datastore adaptation:** when `adapt_datastore: true`, `{{ qac_exe_path }}` is resolved from the active `xc-ce-utils` runtime path. Legacy executable-style `QAC_CONFIG_PATH` entries targeting `_internal/xc_ce_utils/helix_qac` are normalized to the packaged module path.

```yaml
static_analysis:
  type: qac
  create_baseline: false
  strict: true
  sfa: true
  adapt_datastore: false
  artifactory_alias: primary
  baseline_repository_full_path: $ENV{XC_CE_UTILS_REPO_NAME}/qac_baselines/$ENV{XC_CE_UTILS_VARIANT}/files.sup
  target: //sw/...
```

## `sfa` / `sca`

Convenience wrappers around `qac` preconfigured for static-flow / static-code analysis.

```yaml
sfa:
  type: sfa
sca:
  type: sca
  strict: true
```

## `sbom`

- **Behavior:** Runs the SBOM generator with one SBOM configuration file (`config_file`). The generator discovers component manifests, deprecated Fossfiles and third-party SBOM files below `search_dir` (following folder symlinks, skipping `_builds`, `_bin`, `_reports`, `_logs`, `.git`, `.venv*`, `jfrog_cache`), selects the ones used by the variant (see `discovery`), replaces placeholders, validates the manifests and writes the outputs into the step report folder (cleaned before each run).
- **Component manifests:** CSI manifests in the `.metadata` folder of the component, named after the XC SBOM concept: `<component>/.metadata/<name>.product.swelement.manifest.yaml` ([swelement schema](https://sbom.bosch.tech/schemas/v1/product/swelement)) or `<name>.product.tool.manifest.yaml` ([tool schema](https://sbom.bosch.tech/schemas/v1/product/tool), PURL `pkg:bosch.product.tool/...`). One manifest in the folder describes the component; with several, `<component folder>.product.<sub-type>.manifest.yaml` is the component and the others are its subcomponents. The component root is the folder above `.metadata/`; subfolders of `.metadata` (`tpl/`, `last_build/`, `usage/`) are not read. The components form a tree by folder nesting, the topmost one is the project (it needs `projectInformation.projectName` and `projectNumber`). Manifests of the old layout (`sbom/*manifest.sbom.yaml`) fail the step with a hint.
- **Dynamic values:** `$ENV{NAME}` in keys and string values of manifests and Fossfiles is replaced by the environment variable before `replacements` and `set_fields` are applied, e.g. `version: $ENV{RB_VERSION}` or `name: product_$ENV{XC_CE_UTILS_VARIANT_ALIAS}`. An unset variable fails the step and names the file.
- **Repository versions (`repo_versioning`):** each manifest gets the version of the git repository it really lives in (symlinks of a VMR resolved), from `git describe`: tag `v1.0.8` -> `1.0.8`, 9 commits later -> `1.0.9-dev.9+g24acc0c`, uncommitted changes add `+dirty` / `.dirty`. The version replaces the `$ENV{...}` names in `env_variables` and the texts in `placeholders` of that repository's manifests. Rules come from an optional `sbom_versioning.yaml` in the repository (nearest folder up to the git root), else from `repo_versioning.defaults` (`v*.*.*`). Components versioned this way get an `externalReferences` entry of type `vcs` (`git+<remote>@<commit>#<path>`, without credentials); with `variant_qualifier: true` (off by default, components from other repositories are the same for all variants) also `identification.versionSettings` `variant` = the variant alias (PURL qualifier `?variant=...`). A release build (project repository on an exact tag) fails if another repository is untagged. `sbom_versions.json` lists every repository and component version.
- **Checks:** schema validation, name characters (PURL), `description.cycloneDxType`, `description.supplier.name`, the version in the CPE alias. Licenses without own text are looked up in the bundled license catalog (text filled in, unknown licenses fail). Components with the same name and version are reported once (warning).
- **Fields without a manifest counterpart** (`software_type`, `distributed`, `modified`, `entitlement`, `maturity`, `where_bosch_obtained`, comments) are `description.additionalProperties` key/value pairs; `modified` sets the CycloneDX pedigree note.
- **Fossfiles (deprecated):** `Fossfile.json/.yaml/.yml` are still read and converted to manifests, with a warning. `xc-ce-sbom-convert <folder>` writes `.metadata/<name>.product.swelement.manifest.yaml` (one per component and subcomponent) next to each Fossfile.
- **Discovery `compile_db`:** a component or SBOM file is used when a source file or include folder of the compile database or a path from `source_lists` lies in its root folder, when it matches `include_paths`, or when its root is above a used component. Subcomponent manifests follow the manifest of their folder.
- **`include_paths`:** components the build uses but compiles no file of (compilers and their runtime libraries, tools, code generators, SBOM files written by tools, metadata kept outside the component folder) never appear in the build inputs; list them in `include_paths` so they are selected anyway.
- **Discovery `arclbuild`:** same selection, reading the `arclbuild_inputs` folder that arclbuild writes after the CMake configure (`compile_commands.json` and the `files_*.lst` lists with the original source paths, relative to the repo root).
- Build inputs only covered by the project manifest are reported by `uncovered_sources`, grouped by the shallowest folder without a component below it, with the number of files (include folders are not counted).
- **Outputs:** `csi/` (CSI container with `config.json`, project `manifest.yaml`, one `<name>_<version>_manifest.yaml` per component, third-party SBOMs), `SecBOM_SW_ONLY.xlsx`, `sbom_cyclonedx.json`, `sbom_discovery.json` (why each file was included or skipped).
- **CSI vs. SecBOM:** CSI and `sbom_cyclonedx.json` contain the software and, by default, the tools (`*.product.tool.manifest.yaml`, the `tooling` catalog tools; with `tooling.xc_ce_utils` also `xc-ce-utils.cdx.json` in the CSI container). `csi_tools: false` leaves the tools and their subcomponents out. The SecBOM lists everything: all components including the tools, the packages of the `secbom_only_sboms` files and, with `tooling.xc_ce_utils`, the Python packages of xc-ce-utils (`xc-ce-utils.cdx.json`).

Step parameters:

| Field | Default | Description |
|---|---|---|
| `config_file` | required | SBOM configuration file, relative to the repo root. |
| `build_inputs_artifact_type` / `build_inputs_artifactory` | - | CI only: download every zip with this `artifact_type` and the current `variant_alias` from the run's upload folder (`XC_CE_UTILS_ARTIFACTORY_UPLOAD_PATH`) of this artifactory alias and extract it into the `arclbuild_inputs` folder (`arclbuild`) or the folder of `compile_db` (`compile_db`) of the configuration. Fails when nothing is found. |

The environment variable `XC_CE_UTILS_SBOM_RETENTION_POLICY` overrides the `retention_policy` of the configuration (e.g. short retention for develop pushes).

SBOM configuration file (YAML, `$ENV{NAME}` is replaced by the environment variable; all paths and globs are relative to the repo root (`xc-ce-sbom`: the working directory)):

| Field | Default | Description |
|---|---|---|
| `search_dir` | `.` | Folder searched for manifests, Fossfiles and SBOM files; must be inside the repo root. |
| `output_dir` | `sbom_output` | Output folder (cleaned before each run); the step uses its report folder instead. |
| `csi` / `secbom` / `single_cyclonedx` | `false` | Outputs to generate (at least one required). |
| `csi_tools` | `true` | Tools in CSI and `sbom_cyclonedx.json`; `false`: software only, tools in the SecBOM only. |
| `discovery` | `all` | `all` = every discovered file, `compile_db` / `arclbuild` = only files used by the build. |
| `compile_db` / `source_lists` | - / `[]` | `compile_db` discovery: compile database and globs of files listing one used path per line. |
| `arclbuild_inputs` | - | `arclbuild` discovery: folder with `compile_commands.json` and `files_*.lst`. |
| `include_paths` / `exclude_paths` | `[]` | Globs always included / excluded; a pattern also matches the files below a matching folder. `include_paths` selects components without compiled files (tools, compilers, generated-code SBOMs). |
| `uncovered_sources` | `warn` | `ignore`, `warn` or `error` for build inputs not covered by a component. |
| `uncovered_ignore` | `[]` | Globs of build inputs not reported as uncovered, e.g. generated code. They stay part of the project component. |
| `replacements` | `{}` | Placeholder -> value, applied to keys and string values of manifests and Fossfiles (after `$ENV{NAME}`). Empty values are rejected. Prefer `$ENV{NAME}` directly in the manifests. |
| `set_fields` | `{}` | Field -> value, overwrites only fields that already exist (at any depth, e.g. `hardwareVersion`). |
| `retention_policy` | `_UNLIMITED` | CSI retention: `_UNLIMITED`, `_2_WEEKS`, `_1_MONTH`, `_3_MONTHS`, `_6_MONTHS`, `_12_MONTHS`, `_36_MONTHS`. |
| `sbom_glob` | `['*.spdx.json', '*.cdx.json']` | Third-party SBOM files copied into the CSI container. |
| `secbom_only_sboms` | `[]` | Globs of third-party SBOM files (SPDX or CycloneDX JSON) not copied into the CSI container; their packages are listed in the SecBOM only, e.g. SBOMs of tools or SBOMs CSI can't link to the project yet. The files must be selected (`include_paths`). |
| `fossfile_regex` | `Fossfile\.(json\|ya?ml)` | File name regex of the deprecated Fossfiles. |
| `manifest_schema` / `license_catalog` | bundled | Manifest JSON schema and license catalog. |
| `repo_versioning` | - | Per-repository versions (enabled when present, see below). |
| `tooling` | - | Build tools from the xc-ce-utils tool catalog (see below); none without this section. |

`repo_versioning` keys:

| Field | Default | Description |
|---|---|---|
| `enabled` | `true` | `false` keeps the section but disables it. |
| `defaults` | see `sbom_versioning.yaml` | Rules for repositories without `sbom_versioning.yaml` and base of those files; usually `env_variables: [RB_VERSION]`. |
| `variant` | variant of the run | Variant alias for `variants` rules and `versionSettings`; the step sets it, `xc-ce-sbom --variant` outside of an action. |
| `untagged_in_release` | `fail` | `fail`, `warn` or `ignore` when the project repository is on an exact tag but another repository is not. |
| `generate_missing` | `false` | Write `sbom_versioning.yaml` with the defaults into the git root of `search_dir` if missing (commit it). |
| `vcs_url` | `true` | Add the `vcs` external reference. |
| `missing_file` | `ignore` | `ignore`, `warn` or `error` for repositories without `sbom_versioning.yaml`. |
| `outside_repo` | `env` | Manifests outside of git: `env` (global environment) or `error`. |
| `file_name` | `sbom_versioning.yaml` | Name of the rules file. |

```yaml
# sbom_versioning.yaml in a repository (all keys optional)
version:
  source: git_describe      # or env (version from env_variable, e.g. set by CI)
  tag_match: "v*.*.*"       # git describe --match
  tag_prefix: "v"           # removed from the tag
  untagged: next-dev        # next-dev (1.0.9-dev.9+g<sha>) | describe (1.0.8-9-g<sha>) | fail
  prerelease_label: dev
  dirty: mark               # mark | ignore | fail
  remote: origin
env_variables: [RB_VERSION] # $ENV{...} names replaced with this version
placeholders: []            # literal texts replaced with this version
variant_qualifier: false    # true: versionSettings variant / PURL qualifier ?variant=
variants:                   # rule overrides per variant alias, e.g. one tag series per variant
  cgw_cs:
    tag_match: "v1.*"
  cgw_plus:
    tag_match: "v2.*"
```

**Tool catalog (`tooling`):** xc-ce-utils ships manifests of build tools in `xc_ce_utils/sbom/tool_catalog/<name>/`, one folder per `tool_requires` name (`<name>.product.tool.manifest.yaml`, plus subcomponents such as the runtime libraries of a compiler); `tool_catalog.yml` maps `tool_requires` versions to product versions (e.g. Green Hills `comp_202414_1fp_x64` -> `2024.1.4`). The selected tools become tool components below the project, in the project namespace (also in CSI unless `csi_tools: false`, see CSI vs. SecBOM). Available: `greenhills_ifx`, `cmake`, `ninja`, `c_cache`, `hexmodx`, `build_tooling`, `a2lmerger`, `arcl_inv_mngr` and `xc-ce-utils`. Tools without catalog entry are listed in the log; add their manifests to the catalog.

| Field | Default | Description |
|---|---|---|
| `needed_for` | `[build]` | Catalog tools of the variant's `tool_requires` needed for these actions (the step passes the `tool_requires`). |
| `tools` | `{}` | `name: version` added in addition (e.g. for `xc-ce-sbom` outside of an action). |
| `exclude` | `[]` | Tool names not added. |
| `xc_ce_utils` | `false` | Add xc-ce-utils itself (version of the installed package) as a tool and write a CycloneDX of its Python packages (`xc-ce-utils.cdx.json`, listed in the SecBOM and, with `csi_tools`, in the CSI container). Opt-in: the namespace `com/bosch/mobility/compute_enhanced/xc-ce-utils` is a placeholder until CSI assigns one. |

TODO: the PMT SBOM Toolkit (Docker image) could ship its own tool manifest the same way; not implemented.

```yaml
tooling:
  needed_for: [build]
  xc_ce_utils: false
```

```yaml
# actions/sbom.yml - values ending in .yml are config includes, $LITERAL{} keeps the path
generate:
  type: sbom
  config_file: $LITERAL{build_environment/sbom/sbom_config.yml}
  build_inputs_artifact_type: arclbuild_inputs
  build_inputs_artifactory: project_artifactory
```

```yaml
# build_environment/sbom/sbom_config.yml
search_dir: .
csi: true
secbom: true
single_cyclonedx: true
discovery: arclbuild
arclbuild_inputs: _builds/$ENV{XC_CE_UTILS_VARIANT_ALIAS}/build/arclbuild_inputs
include_paths:
  # no file of the compiler is built, so the build inputs never select it
  - build_environment/sbom/**
replacements:
  placeholder_version: $ENV{RB_VERSION}
retention_policy: _UNLIMITED
```

The CLI `xc-ce-sbom --config <file> [--variant <alias>]` runs the generator with a configuration file outside of an action; `--survey-versions` only reports how the repositories of the selected manifests are tagged (`sbom_version_survey.json`).

## Category index

| Step type | Description |
|---|---|
| `docascode` | Sphinx documentation generation |
| `oss` | Open-source license scan (CI-only) |
| `qac` | Generic Helix QAC step |
| `sbom` | SBOM / SecBOM / CSI container generation from Fossfiles |
| `sfa` | Static flow analysis (`qac` preconfigured) |
| `sca` | Static code analysis (`qac` preconfigured) |
