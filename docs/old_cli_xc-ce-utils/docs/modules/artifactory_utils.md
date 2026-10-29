# Artifactory Utils Module

**Package:** `xc_ce_utils.artifactory_utils`
**Purpose:** JFrog Artifactory integration for artifact upload, download, and cleanup

---

## Overview

The `artifactory_utils` package provides three classes for interacting with JFrog Artifactory:

| Class | Module | Description |
|---|---|---|
| `ArtifactoryDownloader` | `artifactory_downloader.py` | Async batch downloads with AQL queries, file-based caching with locking, connection pooling, parallel downloads via `ThreadPoolExecutor` |
| `ArtifactoryUploader` | `artifactory_uploader.py` | File and folder uploads with artifact properties (commit hash, release status, etc.) and target path resolution |
| `ArtifactoryCleaner` | `artifactory_cleaner.py` | REST-based deletion of artifacts (old builds, unused packages) |

All classes authenticate via `RBCredentialsManager` (keyring + environment variable fallback for CI).

---

## ArtifactoryDownloader

High-performance downloader with caching and parallel execution.

**Key features:**
- AQL (Artifactory Query Language) queries for artifact discovery
- File-based cache with `filelock` for concurrent-safe access
- Connection pooling and parallel downloads via `ThreadPoolExecutor`
- Automatic archive extraction

```python
from xc_ce_utils.artifactory_utils.artifactory_downloader import ArtifactoryDownloader

downloader = ArtifactoryDownloader(
    artifactory_url="https://rb-artifactory.bosch.com/artifactory", repository="my-repo"
)

# Download artifacts matching an AQL query
downloader.download_artifacts(
    aql_query='items.find({"repo": "my-repo", "path": {"$match": "*mypackage*"}})',
    target_dir=Path("_tools/mypackage"),
)
```

---

## ArtifactoryUploader

Uploads files and folders with metadata properties.

```python
from xc_ce_utils.artifactory_utils.artifactory_uploader import ArtifactoryUploader
from pathlib import Path

uploader = ArtifactoryUploader(
    artifactory_url="https://rb-artifactory.bosch.com/artifactory",
    repository="libs-release-local",
)

# Upload a single file with properties
uploader.upload_file(
    local_path=Path("_bin/firmware.hex"),
    remote_path="project/v1.0.0/firmware.hex",
    properties={"git.commit": "abc123", "release.status": "released"},
)

# Upload an entire folder
uploader.upload_folder(
    local_folder=Path("_bin/release"), remote_folder="project/v1.0.0"
)
```

---

## ArtifactoryCleaner

REST-based artifact deletion for housekeeping.

```python
from xc_ce_utils.artifactory_utils.artifactory_cleaner import ArtifactoryCleaner

cleaner = ArtifactoryCleaner(
    artifactory_url="https://rb-artifactory.bosch.com/artifactory",
    repository="libs-snapshot-local",
)

# Delete old build artifacts
cleaner.clean_artifacts(path_pattern="project/snapshots/*", older_than_days=30)
```

---

## Integration Points

| Consumer | Usage |
|---|---|
| `tool_installers/` | `ArtifactoryDownloader` fetches tool archives during setup |
| `sw_container_generator/` | Downloads/uploads container build artifacts |
| Core engine deploy steps | Uploads build outputs to release repositories |
| Artifactory MCP server | Exposes search, download, upload operations as MCP tools |

---

## Configuration

Artifactory servers are configured in `config/artifactories/`:

```yaml
# config/artifactories/artifactory_conf.yml
artifactory:
  base_url: "https://rb-artifactory.bosch.com/artifactory"
  repositories:
    tools: "xc-ce-tools-generic-local"
    releases: "libs-release-local"
    snapshots: "libs-snapshot-local"
```

Credentials are resolved automatically â€” keyring for local development, environment variables (`ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD` / `ARTIFACTORY_API_KEY`) in CI.

```python
# Search by properties
artifacts = client.search_artifacts(
    {"build.number": "123", "git.branch": "main", "artifact.type": "jar"}
)

# Search by pattern
maven_jars = client.search_artifacts(
    pattern="*.jar", repository="libs-release", path="com/company/*"
)
```

### Retention Policies

Automated cleanup based on policies:

```yaml
retention_policies:
  - repository: "libs-snapshot"
    rules:
      - older_than: "30 days"
        keep_minimum: 5

  - repository: "docker-local"
    rules:
      - older_than: "90 days"
        keep_latest: 10
        exclude_patterns: ["*-release", "*-stable"]
```

## Security Best Practices

1. **API Key Management**: Store API keys securely, never in source code
2. **Access Control**: Use repository-specific permissions
3. **Network Security**: Always use HTTPS for Artifactory connections
4. **Audit Logging**: Enable audit logs for compliance requirements
5. **Credential Rotation**: Regularly rotate API keys and tokens

## Performance Optimization

1. **Parallel Operations**: Use concurrent uploads/downloads for better throughput
2. **Chunked Transfers**: Split large files into chunks for reliability
3. **Caching**: Implement local caching for frequently accessed artifacts
4. **Compression**: Use artifact compression to reduce transfer times
5. **Network Optimization**: Configure appropriate timeouts and retry policies

## API Reference

### ArtifactoryUploader

Uploads files and folders to JFrog Artifactory repositories using direct HTTP requests.

```{eval-rst}
.. autoclass:: xc_ce_utils.artifactory_utils.artifactory_uploader.ArtifactoryUploader
   :members:
   :undoc-members:
   :show-inheritance:
```

### ArtifactoryDownloader

Enhanced downloader with async/await parallel operations and AQL query support.

```{eval-rst}
.. autoclass:: xc_ce_utils.artifactory_utils.artifactory_downloader.ArtifactoryDownloader
   :members:
   :undoc-members:
   :show-inheritance:
```

### ArtifactoryCache

Thread-safe file-based cache for Artifactory queries with TTL support.

```{eval-rst}
.. autoclass:: xc_ce_utils.artifactory_utils.artifactory_downloader.ArtifactoryCache
   :members:
   :undoc-members:
   :show-inheritance:
```

---

## Used By

### Core Modules

- [Execution Engine](../core_engine/05_building_block_view.md): Automatic artifact publishing during builds
- **conan integration**: Conan package uploads to Artifactory

### Workflows

- **variant-job-action workflow**: Artifact upload after successful builds
- **create-release workflow**: Release artifact publishing

---

## See Also

### Related Modules

- [Execution Engine](../core_engine/05_building_block_view.md): Main build orchestration
- **version management**: Artifact versioning and tagging

### Documentation

- [Getting Started](../guides/getting_started.md)
- [Configuration Guide](../guides/config_guide.md)
