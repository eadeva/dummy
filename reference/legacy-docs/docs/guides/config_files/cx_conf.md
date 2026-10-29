# `cx/cx_conf.yml` — CI-Specific Configuration

`CX_CONFIG` carries values that are visible to actions **only when running in a CI environment**. CI detection is automatic (`CI`, `GITHUB_ACTIONS`, etc.) and triggers a deep-merge of `DEFAULT_PARAMETERS_CX` / `variant_overrides_cx` blocks on top of their non-CX counterparts.

`cx_conf.yml` itself is a free-form dict whose contents are made available to step implementations and `xc-ce-workflows` actions.

## Typical Schema

```yaml
# Pipeline identification
pipeline_name: nightly                  # Read by `only_cx_pipelines` filters
pipeline_kind: scheduled                # e.g. scheduled / pr / release

# Per-pipeline overrides
pipelines:
  nightly:
    actions: [build, doc, sca, sfa, oss]
    upload_artefacts: true
  release:
    actions: [build, doc, sca, sfa, oss, deploy_release]
    upload_artefacts: true
    sign_binaries: true
  pr:
    actions: [build, smoke_test]
    upload_artefacts: false

# Notifier configuration
notifications:
  teams_webhook: $ENV{TEAMS_WEBHOOK}
  on_failure_only: true

# Reporting backends
reports:
  junit_dir: _reports/junit
  upload_artifactory: gw-2wp-generic     # Endpoint key
  upload_path: ci/{{ PROJECT }}/{{ pipeline_name }}/{{ BUILD_NUMBER }}
```

## How CI Overrides Are Applied

Three override layers, all deep-merged when CI is detected:

| Level | Local field | CI override field |
|---|---|---|
| Global / action defaults | `DEFAULT_PARAMETERS` | `DEFAULT_PARAMETERS_CX` |
| Action-level variant override | `variant_overrides` | `variant_overrides_cx` |
| Step-level variant override | `variant_overrides` | `variant_overrides_cx` |

Inside `cx_conf.yml` itself, use `$ENV{VAR_NAME}` substitution to pick up pipeline tokens, webhooks, and runner identifiers without committing secrets.

## `only_cx_pipelines` Filter

Steps and actions can be restricted to specific named pipelines:

```yaml
steps:
  upload_to_dev_repo:
    type: artifactory_upload
    only_cx_pipelines: [nightly, release]
```

The matched pipeline name is `cx_conf.yml::pipeline_name` (resolved from the running CI's pipeline definition).

## Minimal Example

```yaml
pipeline_name: $ENV{CI_PIPELINE_NAME}
notifications:
  teams_webhook: $ENV{TEAMS_WEBHOOK}
```

## See Also

- [Action files](action_file.md) — `DEFAULT_PARAMETERS_CX`, `variant_overrides_cx`
- [main_conf.yml](main_conf.md) — `CX_CONFIG` field
- [CI/CD Workflows](../../workflows/index.md)
