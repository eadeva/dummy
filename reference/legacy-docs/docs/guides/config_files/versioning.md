# `versioning/version.json` — Semantic Version Fields

`RB_VERSIONING` in `main_conf.yml` selects how the project's semantic version is resolved. Three modes are supported:

- **Static file mode** (default): `RB_VERSIONING` is a file reference (or inline dict) to a `version.json` carrying explicit MAJOR/MINOR/BUGFIX fields, manually or CI-maintained.
- **Git-managed mode**: `RB_VERSIONING: git-managed` (a literal string) derives the version from the nearest reachable git tag instead of a static file. See [Git-Managed Mode](#git-managed-mode) below.
- **Variant git-managed mode**: `RB_VERSIONING: variant-git-managed` derives a separate version per variant from its own tag series. See [Variant Git-Managed Mode](#variant-git-managed-mode) below.

Either mode produces the same resolved dict shape, consumed by:

- Step types that embed version info into binaries (e.g. `binary_finalize`, `elf_signature`, custom scripts reading `RB_MAJOR_VERSION`/`RB_MINOR_VERSION`/`RB_BUGFIX_VERSION` env vars)
- The `version-manager` workflow action (`xc-ce-workflows`) — static file mode only
- The CI `commit-tag-push` workflow — static file mode only
- The Artifactory deployer, which adds `commits_ahead`/`full_version_tag` upload properties in git-managed mode (see [deploy step docs](../../core_engine/reference/steps/deploy_reports.md#automatic-property-injection))

## Schema (Static File Mode)

```json
{
  "MAJOR_VERSION": 4,
  "MINOR_VERSION": 19,
  "BUGFIX_VERSION": 0,
  "PRE_RELEASE_SUFFIX": ""
}
```

## Field Reference

| Field | Type | Description |
|---|---|---|
| `MAJOR_VERSION` | int | Major version (breaking changes). |
| `MINOR_VERSION` | int | Minor version (additive changes). |
| `BUGFIX_VERSION` | int | Bugfix/patch version. |
| `PRE_RELEASE_SUFFIX` | str | Pre-release suffix appended to the version string (`-rc1`, `-beta.2`, …); empty for stable. |

## CI Workflow Behaviour

In CI, `version-manager` reads `version.json`, increments according to the pipeline policy, and writes back. The `commit-tag-push` step then commits the change and tags the repo. Manual edits to `version.json` are honoured on the next CI run.

```{important}
The `xc-ce-workflows` pipelines **require** `RB_VERSIONING` to point to a **separate JSON file**. Inlining the version dict into `main_conf.yml` works for local builds but breaks CI versioning. Keep this in its own file.
```

## Per-Variant Versions

A variant can override `version` to point to a different file:

```yaml
variants:
  customer:
    sample:
      alias: cs
      version: ../versioning/customer_version.json
```

This produces customer-specific version numbers in artefacts while leaving the project's master version untouched.

A variant may also omit `version` entirely — it then falls back to the project-wide `RB_VERSIONING` value (static file or git-managed, whichever is active). This is the recommended default; only set a per-variant `version` when that variant genuinely needs an independent version lineage.

## Git-Managed Mode

Set `RB_VERSIONING: git-managed` (a literal string, not a file reference) in `main_conf.yml` to derive MAJOR/MINOR/BUGFIX from git tags instead of maintaining a static `version.json`.

```yaml
RB_VERSIONING: git-managed
```

### How It Works

- The version is resolved from the nearest reachable tag matching `vMAJOR.MINOR.BUGFIX` (lightweight tags), via `git describe --tags --long --match 'v[0-9]*.[0-9]*.[0-9]*'`.
- A custom tag pattern (glob, as `git describe --match`) can be appended after a colon, e.g. `RB_VERSIONING: 'git-managed:release/v*'`. MAJOR.MINOR.BUGFIX is the first `X.Y.Z` in the matched tag name, so prefixed or suffixed tags work too.
- At least one such tag must exist and be reachable from `HEAD` — if none exists, the build fails with an actionable error telling you to create an initial tag (e.g. `git tag v0.0.0 && git push origin v0.0.0`).
- The resolved dict includes the same `MAJOR_VERSION`/`MINOR_VERSION`/`BUGFIX_VERSION` fields as static file mode, plus:

  | Field | Type | Description |
  |---|---|---|
  | `COMMITS_AHEAD` | int | Number of commits since the matched tag. |
  | `COMMIT_HASH` | str | Short commit hash of `HEAD`. |
  | `IS_DIRTY` | bool | `True` if the working tree has uncommitted changes (`git status --porcelain`). |
  | `VERSION_TAG` | str | Name of the matched tag (e.g. `v1.2.3`). |

- Each build action independently recomputes and writes its own `_builds/<variant>/<action>/version.json` snapshot (not committed to the repo — a build artefact only).
- `COMMITS_AHEAD`/`COMMIT_HASH` are also exported as `RB_COMMITS_AHEAD`/`RB_COMMIT_HASH` environment variables, and a composite `RB_FULL_VERSION_TAG` (e.g. `v1.2.3-4-gabc1234`) is exported too — these feed the Artifactory deployer's `commits_ahead`/`full_version_tag` upload properties (absent entirely in static file mode).
- `RB_VERSION_PATTERN` holds the tag pattern in use and is also written to `GITHUB_ENV` in GitHub Actions, so later workflow steps can e.g. find the previous tag of the same series for a changelog.

```{important}
The embedded MAJOR/MINOR/BUGFIX in binaries (e.g. a UDS diagnostic version DID) always reflects the real resolved version — `COMMITS_AHEAD`/dirty state are never substituted in or forced to `0.0.0`. Use `IS_DIRTY` and `COMMITS_AHEAD` from the build metadata (or artifact properties) to distinguish a clean tagged release from an in-development build.
```

### Choosing a Release Version

Use a dispatchable "bump version" workflow (major/minor/bugfix choice) to create and push the next `vMAJOR.MINOR.BUGFIX` tag on top of the highest existing tag — see your project's `dispatch-release-version.yml` (project-specific, not part of `xc-ce-utils` itself).

## Variant Git-Managed Mode

For variants that are released independently (own version series, possibly several tags on the same commit), set:

```yaml
# main_conf.yml
RB_VERSIONING: variant-git-managed        # optional ':<glob>' = pattern of variants without 'version'
```

and give each variant its tag pattern (glob, as `git describe --match`) as `version`:

```yaml
# project_conf.yml
variants:
  cs:
    alias: cgw_cs
    version: 'v1.*'
  plus:
    alias: cgw_plus
    version: 'v2.*'
```

- Each variant resolves its version like [Git-Managed Mode](#git-managed-mode), but only from the tags matching its own pattern: `v1.0.8` and `v2.0.8` on the same commit give `1.0.8` for `cgw_cs` and `2.0.8` for `cgw_plus`.
- `RB_VERSION` (artifact names, Artifactory upload folder, `RB_MAJOR_VERSION`/... and the generated definitions) is the variant's version.
- `RB_COMMITS_AHEAD`, `RB_COMMIT_HASH`, `RB_FULL_VERSION_TAG` and `RB_VERSION_PATTERN` are set per variant.
- The version is resolved when the variant is built, so a variant without a matching tag only fails its own builds.
- `version` must be a tag pattern string in this mode; static version files per variant are not supported.

## Minimal Example

```json
{ "MAJOR_VERSION": 1, "MINOR_VERSION": 0, "BUGFIX_VERSION": 0 }
```

## See Also

- [main_conf.yml](main_conf.md) — `RB_VERSIONING` field
- [Deploy & Reports](../../core_engine/reference/steps/deploy_reports.md) — automatic artifact property injection
- `actions/version-manager` (xc-ce-workflows action) — static file mode only
