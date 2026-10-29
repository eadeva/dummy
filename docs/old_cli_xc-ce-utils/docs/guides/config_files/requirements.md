# Requirements Files — `tool_requires`, `build_requires`, `test_requires`

The `*_requires` keys in `project_conf.yml` reference YAML files that declare project dependencies. Each entry's `type:` field selects one of **three resolver backends**:

| Resolver | `type:` value | What it does |
|---|---|---|
| **Conan** | `conan` (or omitted with Conan-shaped value) | Pulls a Conan package from a Conan-typed artifactory |
| **Artifactory artefact** | `artifact` | Downloads a raw artefact (zip/tar/dir) from a generic Artifactory repository |
| **Toolbase** | declared under `TOOLING.TOOLBASE_TOOLS` | Installs/activates a tool through the local Toolbase manager (Windows) |

```{important}
Conan is **optional**. A project that uses only Artifactory artefacts and Toolbase tools can disable Conan entirely with `CONAN_ENABLED: false` in [`main_conf.yml`](main_conf.md).
```

---

## 1. Conan Resolver

Used for Conan packages. The simplest form is a `name: version_spec` mapping:

```yaml
# requirements/default_build_requires.yml
boost: "[^1.80.0]@thirdparty/stable"
fmt:   "10.2.1@thirdparty/stable"
```

The richer form is a dict per entry (allows pinning vendor, channel, options):

```yaml
my_lib:
  type: conan
  version: "[^2.0.0]"
  vendor: bosch
  channel: stable
  options:
    shared: False
```

### Conan-Typed Artifactory

Resolution requires at least one Conan-typed artifactory in `artifactory_conf.yml`:

```yaml
my-conan:
  type: conan
  url: "https://rb-artifactory.bosch.com/artifactory/api/conan"
  repository: "my-conan-local"
```

Conan setup automatically registers this remote on first invocation. See [artifactory_conf.yml](artifactory_conf.md).

---

## 2. Artifactory Artefact Resolver

Used to download **non-Conan** binaries, libraries, tool snapshots, etc. from a generic Artifactory repository. Each entry has `type: artifact` and declares which artifactory to query:

```yaml
# requirements/default_tool_requires.yml
2wp_cvo-tool:
  type: artifact
  artifactory: gw-2wp-generic         # Key into artifactory_conf.yml
  target_dir: rb_artifacts             # Extraction folder under the project
  no-cache: false                      # Optional: bypass JFrog cache read/write when true
  needed_for:                          # Only download for these actions
    - build
    - sfa
    - sca
  properties:                          # Matrix of Artifactory item-properties to filter by
    rb_version: 1.14.2
    release_status: rel

helix_qac:
  type: artifact
  artifactory: tcc-tools
  target_dir: supplied
  needed_for: [sfa, sca, qac, helix]
  properties:
    rb_version: 2024.2_WIN64
```

### Artefact-Entry Field Reference

| Field | Required | Description |
|---|---|---|
| `type` | yes | Must be `artifact`. |
| `artifactory` | yes | Key into `artifactory_conf.yml`. |
| `target_dir` | yes | Subfolder under the project root where the artefact is extracted. |
| `no-cache` | no | If `true`, bypasses JFrog query cache read/write for this dependency. |
| `needed_for` | no | List of action names. If present, the artefact is downloaded **only** when one of these actions is invoked. Without `needed_for`, the artefact is always downloaded. |
| `properties` | no | Artifactory item-property filters. Selects the matching artefact when multiple revisions exist. |

The download/extract loop is `ArtifactoryInstaller` (see `xc_ce_utils/tool_installers/artifactory_installer.py`).

---

## 3. Toolbase Resolver

Toolbase is the corporate per-user tool-installation manager (Windows). Tools are declared under `TOOLING.TOOLBASE_TOOLS` in the project config (not in a `*_requires` file):

```yaml
TOOLING:
  TOOLBASE_TOOLS:
    default:                           # Toolbase environment name
      Tasking_TriCore:
        version: 6.3r1
        needed_for: [build, sca]
      WinIDEA:
        version: 9.21.234
        needed_for: [debug, test]
    secondary_env:
      AnotherTool:
        version: "1.2.3"
```

### Toolbase-Entry Field Reference

| Field | Required | Description |
|---|---|---|
| `version` | yes | Toolbase-known tool version. |
| `needed_for` | no | List of action names; restricts when the tool is installed/activated. |
| `env_variable` | no | Custom environment-variable name (defaults to `TOOLBASE_<TOOL>`). |

Installation: `xc_ce_utils.tool_installers.toolbase_installer` writes `tb_tools.json` per action+variant, calls Toolbase to install the tools, and writes a `toolbase.env` file that the build step picks up.

---

## Common Pattern (mixed file)

A single requirements file can mix Conan and artefact entries:

```yaml
# requirements/tool_requires_platform.yml
helix_qac:
  type: artifact
  artifactory: tcc-tools
  target_dir: supplied
  properties:
    rb_version: 2024.2_WIN64

clang_tidy:
  type: conan
  version: "[^17.0.0]"
  vendor: thirdparty
  channel: stable
```

## Resolution Order

For each variant, the effective requirements are computed as:

```text
deep_merge(global_defaults.*_requires, variant.*_requires)
```

If both reference files, both files are loaded and **the dicts are deep-merged**. To suppress a global entry per variant, override it with `null` or set conflicting fields.

## See Also

- [project_conf.yml](project_conf.md) — where `*_requires` is referenced
- [artifactory_conf.yml](artifactory_conf.md) — defining the Conan / generic Artifactory endpoints
- [main_conf.yml](main_conf.md) — `CONAN_ENABLED` toggle
