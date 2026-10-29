# RTC Client Wrapper Module

**Package:** `xc_ce_utils.rtc_client_wrapper`
**Purpose:** Integration with IBM Rational Team Concert (RTC/Jazz) for work item management

---

## Overview

The `rtc_client_wrapper` package contains two implementations for interacting with IBM RTC:

| Module | Class | Description |
|---|---|---|
| `bosch_rtc_client.py` | `BoschRTCClient` | **Primary.** Full-featured OSLC client for work item CRUD, queries, state transitions, iteration resolution, and user lookup. |
| `rtc_client_wrapper.py` | `RTCClientWrapper` | **Legacy.** Thin wrapper around the `rtcclient` library providing basic title/owner lookup. |

`BoschRTCClient` is the active implementation used by MCP servers and CI/CD tooling. The legacy wrapper remains for backwards compatibility.

---

## BoschRTCClient (Primary)

### Key Capabilities

- **Work Item CRUD** — create, read, update (single field or multi-field), copy work items
- **OSLC Queries** — flexible `oslc.where` queries with pagination (100 results/page, auto-paged)
- **State Transitions** — RDF/XML partial update with `_action` query parameter (the only method that reliably changes state via OSLC)
- **Iteration Resolution** — resolve sprint names (e.g. `SP03_26`) to OSLC iteration URIs
- **User Resolution** — resolve usernames to full OSLC contributor URIs
- **Saved Queries** — discover and execute RTC saved queries by name
- **Task Workflows** — `close_task`, `replan_task`, `copy_workitem` with precondition handling

### Authentication

Credentials are managed via `RBCredentialsManager`:

- **Interactive (local):** Keyring-based storage, prompts on first use
- **CI/CD:** Reads from environment variables (`RTC_USERNAME`, `RTC_PASSWORD`) with auto-detection

```python
from xc_ce_utils.rtc_client_wrapper.bosch_rtc_client import BoschRTCClient

client = BoschRTCClient(
    server_url="https://rb-alm-14-p.de.bosch.com/ccm", project_name="My Project Area"
)
```

### State Transition Mechanism

RTC OSLC does **not** support state changes via simple field updates. `BoschRTCClient` uses:

1. `GET` the work item with `Accept: application/rdf+xml`
2. `PUT` the same RDF/XML body back with `?_action={workflow}.action.{action_name}`

**Task Workflow Map** (`com.ibm.team.workitem.taskWorkflow`):

| From | Action | To | Preconditions |
|---|---|---|---|
| New (s1) | `startWorking` | In Progress (s2) | Owner must be set |
| In Progress (s2) | `resolve` | Closed (s3) | `timeSpent > 0` |
| In Progress (s2) | `a5` | Ready for Review (s5) | — |
| In Progress (s2) | `a2` | Invalid (s4) | — |
| Ready for Review (s5) | `a1` | In Progress (s2) | — |
| Closed (s3) | `a1` | In Progress (s2) | — |
| Invalid (s4) | `a4` | New (s1) | — |

### Usage Examples

```python
# Get a work item
wi = client.get_workitem_by_id("1234567")
print(wi["title"], wi["owner"], wi["state"])

# OSLC query
results = client.query_workitems('dcterms:contributor=<...> and dcterms:type="task"')

# Update fields
client.update_workitem_field("1234567", "title", "New Title")
client.update_workitem_multiple_fields(
    "1234567", {"title": "New", "rtc_cm:estimate": "8"}
)  # 8 hours

# Close a task (handles New → In Progress → Closed transitions)
client.close_task("1234567")

# Replan to next sprint (splits if time spent > 0)
client.replan_task("1234567", "SP04_26")

# Resolve sprint name to URI
uri = client.resolve_iteration("SP03_26")
```

---

## RTCClientWrapper (Legacy)

Thin wrapper around the third-party `rtcclient` library. Provides a single method:

```python
from xc_ce_utils.rtc_client_wrapper.rtc_client_wrapper import RTCClientWrapper

rtc = RTCClientWrapper()
title, owner = rtc.get_wi_title_and_owner("12345")
```

Use `BoschRTCClient` for any new development.

---

## Integration Points

| Consumer | Usage |
|---|---|
| `mcp/rtc/` MCP server | Exposes `BoschRTCClient` operations as MCP tools (query, create, update, close, replan) |
| `rtc_github/rtc_linker.py` | Links GitHub PRs/commits to RTC work items in CI/CD |
| Git hooks | Validates commit messages contain valid RTC work item IDs |

---

## Configuration

Project-level RTC settings are defined in a YAML config file referenced by the `RTC_PROJECT_CONFIG` environment variable:

```yaml
server_url: "https://rb-alm-14-p.de.bosch.com/ccm"
default_project: "My Project Area"
saved_queries:
  - "Open Tasks for Sprint"
  - "My Open Defects"
queries:
  my_open_tasks:
    query: 'dcterms:contributor=<{current_user}> and dcterms:type="task"'
    exclude_states: ["Closed", "Invalid"]
```
        print(f"Linked build {build_id} to {len(traceability['work_items'])} work items")
```

### Release Notes Generation

Generate release notes from RTC work items:

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper
from datetime import datetime

def generate_release_notes(work_item_ids, version):
    """Generate release notes from work item titles."""
    rtc = RTCClientWrapper()

    notes = [
        f"# Release Notes - Version {version}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Features and Fixes",
        ""
    ]

    for wi_id in work_item_ids:
        title, owner = rtc.get_wi_title_and_owner(wi_id)
        if title:
            notes.append(f"- [{wi_id}] {title} (Owner: {owner})")

    release_notes = "\n".join(notes)

    with open(f'RELEASE_NOTES_{version}.md', 'w') as f:
        f.write(release_notes)

    return release_notes

# Usage
work_items_in_release = ["12345", "12346", "12350"]
notes = generate_release_notes(work_items_in_release, "v2.1.0")
print(notes)
```

### Pre-Deployment Validation

Validate work items before deployment:

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper


def validate_deployment_readiness(work_item_ids):
    """Ensure all work items are valid before deployment."""
    rtc = RTCClientWrapper()
    errors = []

    for wi_id in work_item_ids:
        title, owner = rtc.get_wi_title_and_owner(wi_id)

        if not title:
            errors.append(f"Work item {wi_id} not found")
        elif not owner:
            errors.append(f"Work item {wi_id} has no owner assigned")

    if errors:
        raise ValueError(
            f"Deployment validation failed:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )

    return True


# Usage in deployment pipeline
try:
    work_items = ["12345", "12346"]
    validate_deployment_readiness(work_items)
    print("✓ All work items validated for deployment")
    # Proceed with deployment
except ValueError as e:
    print(f"✗ Deployment blocked: {e}")
    sys.exit(1)
```

---

## Advanced Features

### Custom RTC Queries

While the wrapper currently provides basic work item retrieval, the underlying `rtcclient` library supports advanced queries:

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper

rtc_wrapper = RTCClientWrapper()
rtc_client = rtc_wrapper.rtc_client  # Access underlying client

# Example: Custom query (requires extending RTCClientWrapper)
# myquery = rtc_client.query
# projectarea_name = "MyProject"
# myquerystr = 'dc:title="Feature Request"'
# returned_prop = "dc:title,dc:identifier,rtc_cm:state,rtc_cm:ownedBy"
#
# queried_wis = myquery.queryWorkitems(
#     query_str=myquerystr,
#     projectarea_name=projectarea_name,
#     returned_properties=returned_prop
# )
```

### Multi-Project Access

Connect to different RTC project areas:

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper

# Project A
rtc_project_a = RTCClientWrapper(url="https://rtc-a.company.com/ccm")
title_a, owner_a = rtc_project_a.get_wi_title_and_owner("A-123")

# Project B
rtc_project_b = RTCClientWrapper(url="https://rtc-b.company.com/ccm")
title_b, owner_b = rtc_project_b.get_wi_title_and_owner("B-456")
```

---

## Error Handling

### HTTP Authentication Errors

The wrapper automatically handles 401 authentication errors:

```python
try:
    rtc = RTCClientWrapper()
    title, owner = rtc.get_wi_title_and_owner("12345")
except HTTPError as e:
    if e.response.status_code == 401:
        # Automatic password refresh attempted
        print("Authentication failed, password may need to be re-entered")
    else:
        print(f"HTTP error occurred: {e}")
```

### Work Item Not Found

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper

rtc = RTCClientWrapper()
title, owner = rtc.get_wi_title_and_owner("invalid_id")

# Returns empty strings if work item not found
if not title and not owner:
    print("Work item not found or access denied")
```

### Connection Failures

```python
from xc_ce_utils.rtc_client_wrapper import RTCClientWrapper
from requests.exceptions import ConnectionError, Timeout

try:
    rtc = RTCClientWrapper(url="https://unreachable.rtc.server/ccm")
    title, owner = rtc.get_wi_title_and_owner("12345")
except ConnectionError:
    print("Cannot connect to RTC server - check network and URL")
except Timeout:
    print("RTC server request timed out")
```

---

## Configuration

### Environment Variables

Configure RTC connection via environment:

```bash
# Set RTC server URL
export RTC_URL="https://rtc.company.com/ccm"

# Use in code
rtc_url = os.getenv('RTC_URL', 'https://rb-alm-14-p.de.bosch.com/ccm')
rtc = RTCClientWrapper(url=rtc_url)
```

### Password Storage Location

Passwords are stored in OS keyring:

| OS | Location |
|----|----------|
| **Windows** | Windows Credential Manager |
| **macOS** | Keychain |
| **Linux** | Secret Service (GNOME Keyring, KWallet) |

**Manual Password Reset:**
```python
from pathlib import Path
import os

# Remove stored password (forces re-prompt)
home = Path.home()
password_file = home / ".rtc" / "rtc.pass"
if password_file.exists():
    os.remove(password_file)
```

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Link Build to RTC Work Items
  env:
    RTC_URL: ${{ secrets.RTC_URL }}
    RTC_USERNAME: ${{ secrets.RTC_USERNAME }}
    RTC_PASSWORD: ${{ secrets.RTC_PASSWORD }}
  run: |
    python scripts/link_work_items.py --build-id ${{ github.run_id }}
```

### Azure DevOps

```yaml
- task: PythonScript@0
  inputs:
    scriptSource: 'filePath'
    scriptPath: 'scripts/validate_work_items.py'
    arguments: '--work-items $(WorkItems)'
  env:
    RTC_URL: $(RTCServerUrl)
    RTC_PASSWORD: $(RTCPassword)
```

---

## Best Practices

### 1. Cache RTC Client Instance

Reuse client instance across multiple queries:

```python
class WorkItemManager:
    def __init__(self):
        self._rtc = None

    @property
    def rtc(self):
        if self._rtc is None:
            self._rtc = RTCClientWrapper()
        return self._rtc

    def get_work_items(self, ids):
        results = []
        for wi_id in ids:
            title, owner = self.rtc.get_wi_title_and_owner(wi_id)
            results.append((wi_id, title, owner))
        return results
```

### 2. Handle Missing Work Items Gracefully

```python
def safe_get_work_item(rtc, work_item_id):
    """Safely retrieve work item with error handling."""
    try:
        title, owner = rtc.get_wi_title_and_owner(work_item_id)
        if not title:
            return None
        return {"id": work_item_id, "title": title, "owner": owner}
    except Exception as e:
        logger.warning(f"Failed to retrieve work item {work_item_id}: {e}")
        return None
```

### 3. Validate Work Item IDs

```python
import re


def is_valid_work_item_id(wi_id):
    """Validate work item ID format."""
    # Adjust regex based on your RTC instance format
    return bool(re.match(r"^\d+$", str(wi_id)))


# Usage
work_item_id = "12345"
if is_valid_work_item_id(work_item_id):
    rtc = RTCClientWrapper()
    title, owner = rtc.get_wi_title_and_owner(work_item_id)
```

### 4. Log Work Item Access

```python
from xc_ce_utils import logger


def get_work_item_with_logging(rtc, work_item_id):
    """Retrieve work item with audit logging."""
    logger.info(f"Querying RTC work item: {work_item_id}")

    title, owner = rtc.get_wi_title_and_owner(work_item_id)

    if title:
        logger.info(f"Retrieved work item {work_item_id}: {title}")
    else:
        logger.warning(f"Work item {work_item_id} not found")

    return title, owner
```

---

## Troubleshooting

### Authentication Failures

**Symptom:** 401 Unauthorized errors

**Solutions:**
1. Verify credentials are correct
2. Check RTC server URL is accessible
3. Ensure user has permissions to access work items
4. Clear stored password: `rm ~/.rtc/rtc.pass`
5. Re-enter password on next connection attempt

### Connection Timeouts

**Symptom:** Requests hanging or timing out

**Solutions:**
1. Check network connectivity to RTC server
2. Verify firewall/proxy settings
3. Test RTC URL in browser
4. Contact RTC administrator for server status

### Work Items Not Found

**Symptom:** Empty title/owner returned

**Solutions:**
1. Verify work item ID exists in RTC
2. Check user has read permissions for project area
3. Ensure work item is not archived/deleted
4. Confirm correct RTC server URL

### Password Storage Issues

**Symptom:** Password not persisting between runs

**Solutions:**
1. Check keyring is available: `pip show keyring`
2. Install platform-specific keyring backend
3. Verify `~/.rtc/` directory permissions
4. Use environment variables as fallback

---

## See Also

- [RTC GitHub Linker](rtc_github.md) - GitHub-RTC work item linking
- Password Handler - Secure credential management
- RTC GitHub Integration - GitHub-RTC synchronization
- [Global Modules](global_modules.md) - Utility functions
