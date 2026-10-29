# RTC GitHub Linker

**Package:** `xc_ce_utils.rtc_github`
**Purpose:** GitHub-to-ALM RTC work item linking for CI/CD pipelines

## Overview

Validates that GitHub PRs, commits, and issue comments reference valid RTC (Rational Team Concert) work items. Automatically adjusts commit/PR messages to comply with ALM linking format, extracts work item IDs from branch names as fallback, and prevents linking to closed, cancelled, or invalid items. Designed to run as a GitHub Actions step.

## Module

| Module | Description |
|---|---|
| `rtc_linker.py` | `GitEventHandler` — main handler for GitHub event processing |

## GitEventHandler

```python
handler = GitEventHandler(
    alm_server_url="https://rtc.example.com/ccm",
    alm_repo_key="PROJECT_KEY",
    payload=github_event_payload,
    alm_rtc_user="user",
    alm_rtc_user_token="token",
    alm_project_area_id="project-area-uuid",
    max_chars=65535,
    fail_on_missing_wi=True,
    adjust_input_message=True,
)
```

### Methods

| Method | Description |
|---|---|
| `modify_payload(branch_wi_ids)` | Adjust PR/commit/comment messages for ALM linking format |
| `_get_pr_commit_messages()` | Extract commit messages via `git log` |
| `_get_branch_name()` | Extract source branch from payload |
| `_extract_branch_workitem_ids()` | Extract WI IDs from branch name patterns |

## Supported GitHub Events

| Event | Regex Pattern |
|---|---|
| `push` | `PUSH_WORKITEMS_REGEX` |
| `pull_request` | `PULL_REQUEST_WORKITEMS_REGEX` |
| `issue_comment` | `ISSUE_COMMENT_WORKITEMS_REGEX` |

Branch names matching `BRANCH_WORKITEM_REGEX` serve as a fallback source for work item IDs.

## GitHub Action Integration

Configured via environment variables in the `actions/rtc-linker/action.yml` composite action:

| Variable | Description |
|---|---|
| `ALM_SERVER_URL` | RTC server base URL |
| `ALM_REPO_KEY` | Repository key for ALM linking |
| `ALM_PROJECT_AREA_ID` | RTC project area UUID |
| `PAYLOAD` | Full GitHub event payload JSON |
| `ALM_RTC_USER` | RTC service account username |
| `ALM_RTC_USER_TOKEN` | RTC authentication token |

## Dependencies

- **External:** `requests`
- **Internal:** none (uses standard `logging`)

## See Also

- [RTC Client Wrapper](rtc_client_wrapper.md) — full RTC OSLC client for work item management
- [Actions Reference](../workflows/actions_reference.md) — `rtc-linker` GitHub Action
