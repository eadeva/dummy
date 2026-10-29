# Deploy & Reports

Artifact deployment, cleanup, and JUnit aggregation.

## `deploy`

- **CI-only.**
- **Source:** [`deploy_steps.py`](../../../../xc_ce_utils/core_engine/steps/deploy_steps.py)
- **Behavior:** Delegates to `Deployer.deploy(config['deployments'])` (copy, zip, Artifactory upload, …).

```{uml} ../../../_diagrams/artifactory_uploader.puml
:caption: Deployer.deploy() flow — path resolution, per-deployment upload, and PR comment posting.
```

### Breaking Path Contract

- Computed base paths no longer include commit hash.
- Computed base paths always include a semantic-version sortable segment.
- For non-PR events, deployer always resolves the latest reachable git tag
  (`git describe --tags --abbrev=0`) and uploads to `.../tags/...`.
- If no reachable tag exists for a non-PR run, deploy fails.
- Tag uploads use a single folder level under `.../tags/` in this format:
  `repo/tags/0002.0008.0000__v2.8.0`
  where the text after `__` is the full tag value (sanitized for path safety).
- Legacy deploy parameters `only_relative_path` and `upload_rel_path` are removed.
- Use `repository_full_path` for an explicit repository-relative target path.

### Supported Deployment Parameters

- `path` (required): local source path or glob.
- `artifactory` (required): Artifactory alias (comma-separated supported).
- `zip` (optional): whether to zip before upload.
- `zip_name` (required when `zip: true`): zip filename without extension.
- `properties` (optional): Artifactory properties.
- `repository_full_path` (optional): explicit repository-relative destination; bypasses computed base path.
- `docs_publishing` (optional): extra docs zip publish path for tag builds.

### Automatic Property Injection

The deployer automatically injects standard XC-CE metadata properties on top of any user-specified properties:

- `commit_hash`: Short 8-character Git commit hash of HEAD.
- `long_commit_hash`: Full 40-character Git commit hexsha.
- `rb_artifact`: Sourced from the `XC_CE_UTILS_ARTIFACT` environment variable (defaults to `unknown`).
- `release_status`: Sourced from the `XC_CE_UTILS_RELEASE_STATUS` environment variable (defaults to `local`).
- `git_is_dirty`: Sourced from the `GIT_COMMIT_IS_DIRTY` environment variable (defaults to `false`).
- `action`: Name of the build action being executed (e.g., `build`, `doc`, `oss`).
- `branch`: Sourced primarily from the `XC_CE_UTILS_BRANCH_NAME` environment variable, falling back to the detected Git/CI branch context, and defaulting to `'unknown'`.
- `pr_number`: Only injected for CI builds triggered by a pull-request event (absent otherwise).
- `commits_ahead`: Only injected when `RB_VERSIONING: git-managed` is active (see [versioning.md](../../../guides/config_files/versioning.md#git-managed-mode)) — number of commits since the nearest reachable version tag. Absent entirely in static `version.json` mode.
- `full_version_tag`: Only injected when `RB_VERSIONING: git-managed` is active — the full `git describe` style tag (e.g. `v1.2.3-4-gabc1234`). Absent entirely in static `version.json` mode.

### Removed Parameters

- `only_relative_path`
- `upload_rel_path`

Using removed parameters causes the deploy step to fail.

```yaml
publish:
  type: deploy
  deployments:
    binaries:
      artifactory: primary
      zip: true
      zip_name: firmware_$ENV{RB_VERSION}
      path: _bin/firmware
      properties:
        rb_version: $ENV{RB_VERSION}
```

```yaml
publish_fixed_path:
  type: deploy
  deployments:
    baseline:
      artifactory: primary
      path: baseline/files.sup
      repository_full_path: my_repo/qac_baselines/$ENV{XC_CE_UTILS_VARIANT}/files.sup
```

## `artifactory_cleanup`

- **CI-only.**

```yaml
prune_artifactory:
  type: artifactory_cleanup
  artifactory_alias: primary
  removal_path: firmware/old_release/
```

## `splunk_export`

- **Source:** [`deploy_steps.py`](../../../../xc_ce_utils/core_engine/steps/deploy_steps.py)
- **Behavior:** Copies one or more local export files to a shared network destination built as:
  - base: `SPLUNK.shared_network_drive_path` from `config/main_conf.yml`
  - target (per source file):
    `<base>/<shared_folder_rel_path>/<project_name>_<source_name_without_ext>_<YYYY-MM-DD_HH-mm><source_ext>`
- **Also generates:** `<project_name>_MD.json` in the same target folder, but only
  if it doesn't already exist - the metadata file is never deleted or overwritten by a later run
  (the shared per-release folder may be written to by several independent actions/re-runs).
- **UNC / SMB shares:** when `shared_network_drive_path` is a UNC path (`\\server\share\...` or
  `//server/share/...`), the step authenticates over SMB via `smbclient` instead of relying on
  plain filesystem access - required for CI runners/containers that have no OS-level session to
  the host. Credentials are resolved through `xc_ce_utils.auth.get_credentials_manager()`
  (`TECHNICAL_USER_ID`/`TECHNICAL_USER_PASSWORD` in CI, keyring/interactive prompt locally) for
  `smb://<server>`. Non-UNC (plain local/mapped-drive) paths still use direct filesystem calls,
  unchanged. Directory creation retries past a transient `STATUS_DELETE_PENDING` (a folder still
  finishing an in-flight deletion) with exponential backoff, up to ~130s total.

### Parameters

- `file_paths` (required): non-empty list of source file paths (absolute or repo-relative).
- `shared_folder_rel_path` (required): relative destination path under the shared network drive.
- `remove_old_files` (optional, default `false`): before writing each new (non-metadata) file,
  delete any existing files in the target folder matching that same source file's
  `<project_name>_<stem>_*<ext>` pattern (or `<project_name>_<kind>_*.csv` per `code_metrics`
  category). Scoped to the stem being written, so sibling exports sharing the same folder (e.g.
  MV/SV/CCV together) are left untouched. The metadata file is never affected.
- `release_level1` (optional): value for `ReleaseLevel1.Name` in the metadata file. Default:
  `$ENV{XC_CE_UTILS_VARIANT_ALIAS}`.
- `release_level2` (optional): value for `ReleaseLevel2.Name` in the metadata file. Default:
  `$ENV{RB_VERSION}`.

Generated metadata payload (defaults shown; empty `release_level*` values also use the default):

```json
{
  "MetaDataVersion": "1",
  "TimeStamp": 1782119641,
  "ReleaseLevel1": {
    "Name": "<$ENV{XC_CE_UTILS_VARIANT_ALIAS}>",
    "Default": true
  },
  "ReleaseLevel2": {
    "Name": "<$ENV{RB_VERSION}>",
    "Default": true
  }
}
```

```yaml
# config/main_conf.yml
SPLUNK: splunk/splunk_conf.yml
```

```yaml
# config/splunk/splunk_conf.yml
shared_network_drive_path: "\\\\server\\share\\splunk"
```

```yaml
export_dashboard_json:
  type: splunk_export
  file_paths:
    - _reports/xc-ce/splunk-dac/dashboard.json
    - _reports/xc-ce/splunk-dac/summary.txt
  shared_folder_rel_path: project_a/release_1
  release_level1: TOYOTA_CGW          # optional, default: variant alias
  release_level2: $ENV{RB_VERSION}    # optional, default: RB_VERSION
```

## `test_report_collect`

- **Source:** [`report_steps.py`](../../../../xc_ce_utils/core_engine/steps/report_steps.py)
- **Behavior:** Aggregates JUnit XMLs via `TestReportCollector` and emits merged JUnit / HTML / PDF.

```yaml
collect_reports:
  type: test_report_collect
  reports_dir: _reports
  output_formats: [junit, html]
  output_dir: _reports/aggregated
  report_name: test_report
  glob_pattern: "**/*.xml"
```

## Category index

| Step type | Description |
| --- | --- |
| `deploy` | Deploy artefacts (CI-only) |
| `artifactory_cleanup` | Remove old Artifactory artefacts (CI-only) |
| `splunk_export` | Copy export files to configured shared Splunk path |
| `test_report_collect` | Aggregate JUnit XML into JUnit/HTML/PDF |
