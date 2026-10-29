# Repo Dependency Handler

**Package:** `xc_ce_utils.repo_dependency_handler`
**Purpose:** Multi-repository Git dependency resolution with parallel cloning

## Overview

Reads JSON dependency manifests specifying repositories with branch/tag/commit targets, then clones and checks out dependencies in parallel. Uses file locking to prevent race conditions in concurrent builds. Detects version inconsistencies and dirty working trees.

## Modules

| Module | Description |
|---|---|
| `repo_dependency_resolver.py` | Parallel dependency resolver (current) â€” `resolve_dependencies()` |
| `repo_dependency_handler.py` | Legacy recursive dependency walker â€” `find_dependencies_and_clone()` |
| `git_helper.py` | `GitHelper` and `RepoLock` classes for safe Git operations |

## Key Classes and Functions

### resolve_dependencies()

Main entry point. Reads a JSON dependency file and clones/checks-out repos in parallel:

```python
resolve_dependencies(dependencies_file_path, clean=False)
```

Uses `ThreadPoolExecutor` for parallel cloning.

### GitHelper

Git operations wrapper:

```python
helper = GitHelper(repo_path, repo_url, branch="main", commit=None, tag=None)
```

Methods: clone, checkout, verify integrity.

### RepoLock

Cross-platform file-lock context manager for concurrent repo access:

```python
with RepoLock(repo_path, timeout=60, poll_interval=1):
    # safe repo operations
```

### UnexpectedRepoChanges

Exception raised when detecting dirty working trees or version mismatches.

## Dependency File Format

```json
{
  "dependencies": [
    {
      "url": "https://github.example.com/org/repo.git",
      "branch": "main",
      "commit": "abc1234",
      "tag": "v1.0.0",
      "target_folder": "../repo"
    }
  ]
}
```

Only one of `branch`, `commit`, or `tag` is required.

## Build Engine Integration

Called by `ExecutionAction` during pre-build initialization (imported as `rep_resolver`) to resolve repository dependencies before build phases execute. Not a registered step type â€” integrated directly into the execution engine startup.

## Dependencies

- **External:** `GitPython`
- **Internal:** `xc_ce_utils.json_utils`

## See Also

- [Core Engine â€” Execution Engine](../core_engine/05_building_block_view.md) â€” the engine that invokes the resolver during pre-build init
- [JSON Utils](json_utils.md) â€” underlying JSON loader
- [Conf File Loader](conf_file_loader.md) â€” sibling configuration loader
