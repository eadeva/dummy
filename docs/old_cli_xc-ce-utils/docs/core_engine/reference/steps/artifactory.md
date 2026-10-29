# Artifactory Steps

Downloader instances live in `self.resources["artifactory_downloaders"]`.

```{uml} ../../../_diagrams/artifactory_downloader.puml
:caption: art_downloader_setup / art_download / art_download_central flow.
```

## `art_downloader_setup`

- **Source:** [`artifactory_steps.py`](../../../../xc_ce_utils/core_engine/steps/artifactory_steps.py)
- **Shape:** PARAMS-DICT — all fields are nested under `params:`, not flat.

```yaml
art_setup:
  type: art_downloader_setup
  params:
    id: primary
    base_url: https://artifactory.example.com
    repository: generic-local
    download_path: _downloads
```

## `art_download`

- **Behavior:** Resolves and downloads an artifact, exporting `os.environ["ARTIFACT_<id>"]`. Honors `ARTIFACT_<download_id>_SOURCE` env override: `"local"` (read path from `ARTIFACT_<id>`) or `"remote"` (use version from `ARTIFACT_<id>_VERSION`).
- **Cache Policy & Freshness Checks:**
  - **With `latest: true`**: Always queries Artifactory to find the newest matching artifact (bypassing the local query cache). If the newest artifact's name or creation timestamp has changed compared to `.artifact_meta.json`, the old folder is deleted and the new build is downloaded.
  - **With `latest: false`**: Instead of relying solely on directory physical existence, the downloader parses `.artifact_meta.json` and performs key-value comparison against requested property filters. If the metadata file is missing, corrupted, or any property value mismatches, the directory is deleted and a fresh download of the exact configured version is performed.
- **Handling Duplicate Artifacts:**
  - If multiple artifacts share the exact same property filters:
    - **`latest: true`**: Sorts them by semantic version (`rb_version`) first, and falls back to `created`/`modified` timestamps (newest wins).
    - **`latest: false`**: Bypasses semantic version sorting and deterministically selects the newest artifact based strictly on its `created` and `modified` timestamps.

```yaml
get_compiler:
  type: art_download
  params:
    downloader_id: primary
    download_id: compiler
    type: artifact
    art_rel_path: tools/compiler/
    latest: true
    no_cache: false
    properties:
      os: windows
    target_dir: _downloads/compiler
    output_variable: COMPILER_DIR
```

## `art_download_central`

Same fields as `art_download`; `central_path` is always forced to `true` (machine-wide
`C:\tools/<target_dir>` destination instead of the downloader's `download_path`).

```yaml
get_shared_lib:
  type: art_download_central
  params:
    downloader_id: primary
    download_id: shared_lib
    art_rel_path: shared/libs/foo/1.2.3/foo.zip
    target_dir: _downloads/foo
    output_variable: FOO_DIR
```

## Category index

| Step type | Description |
|---|---|
| `art_downloader_setup` | Configure an Artifactory downloader |
| `art_download` | Download an artifact (resolved via properties) |
| `art_download_central` | Download from a fixed central path |
