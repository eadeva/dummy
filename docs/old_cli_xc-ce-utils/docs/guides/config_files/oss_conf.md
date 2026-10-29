# `oss/oss_conf.yml` â€” Open-Source Scanning Configuration

`OSS_CONFIG` controls the open-source-software (OSS) scanning action. It declares which scanner to use, which sources to scan, license-policy decisions, and how/where to publish reports.

```{note}
OSS scanning is an optional feature. Projects that do not consume third-party source code do not need this file.
```

## Schema

```yaml
scanner: fossology                       # or: black-duck, scancode

# Scan inputs
scan_sources:
  - SW/                                   # Glob or directory
  - third_party/**

# Inclusions / exclusions
include_patterns:
  - "*.c"
  - "*.h"
  - "*.cpp"
exclude_patterns:
  - "**/test/**"
  - "**/_build/**"

# License policy
license_policy:
  allow:
    - Apache-2.0
    - MIT
    - BSD-3-Clause
  forbid:
    - GPL-3.0
    - AGPL-3.0
  review_required:
    - LGPL-2.1

# Output
report_dir: _reports/oss
formats: [html, junit, csv]

# Publishing
publish:
  artifactory: gw-2wp-generic
  path: oss/{{ PROJECT }}/{{ FULL_VERSION }}
  on: [release, nightly]                 # only_cx_pipelines

# Scanner-specific options pass through to the implementation
scanner_options:
  fossology:
    server_url: $ENV{FOSSOLOGY_URL}
    api_token: $ENV{FOSSOLOGY_TOKEN}
    folder_id: 42
  black-duck:
    project: "{{ PROJECT }}"
    version: "{{ FULL_VERSION }}"
    server_url: $ENV{BLACKDUCK_URL}
    api_token: $ENV{BLACKDUCK_TOKEN}
```

## Field Reference

| Field | Required | Description |
|---|---|---|
| `scanner` | yes | Scanner backend. |
| `scan_sources` | yes | Directories or glob patterns to scan. |
| `include_patterns` | no | Restrict scan to files matching these patterns. |
| `exclude_patterns` | no | Exclude files matching these patterns. |
| `license_policy.allow` | no | Whitelisted SPDX identifiers; non-listed licences trigger a finding. |
| `license_policy.forbid` | no | Blacklisted SPDX identifiers; finding fails the action. |
| `license_policy.review_required` | no | Licences that must be manually approved. |
| `report_dir` | no | Where to write reports. Default: `_reports/oss`. |
| `formats` | no | Output formats (`html`, `junit`, `csv`, `sarif`, â€¦). |
| `publish.artifactory` | no | Artifactory endpoint key for report upload. |
| `publish.path` | no | Upload path template. |
| `publish.on` | no | Pipelines that trigger upload. |
| `scanner_options` | no | Free-form options forwarded to the chosen scanner. |

## Action Invocation

The OSS action is typically declared in `actions_conf.yml` as `oss: oss.yml` and the action file invokes the `oss` step type:

```yaml
# actions/oss.yml
description: "OSS license scan"
steps:
  scan:
    type: oss
```

## See Also

- [main_conf.yml](main_conf.md) â€” `OSS_CONFIG` field
- [Step Reference](../../core_engine/reference/step_reference.md) â€” `oss` step
