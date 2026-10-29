# `artifactory_conf.yml` — Artifactory Endpoints

Defines the Artifactory repositories used by the project. Each top-level key is a **logical name** referenced from elsewhere (typically from requirements files and Conan remote setup).

## Schema

```yaml
# Generic Artifactory repository (default type)
gw-2wp-generic:
  url: "https://rb-artifactory.bosch.com:443/artifactory/"
  repository: "gw-2wp-generic-local"

# Conan-typed Artifactory repository
gw-2wp-conan:
  type: conan
  url: "https://rb-artifactory.bosch.com/artifactory/api/conan"
  repository: "gw-2wp-conan-local"

# Third-party tool repository
tcc-tools:
  url: "https://rb-artifactory.bosch.com:443/artifactory/"
  repository: "tcc-tools-local"

# With explicit authentication overrides (rare — usually keyring is used)
explicit-auth-example:
  url: "https://example.com/artifactory/"
  repository: "my-repo"
  auth:
    env_user: MY_REPO_USER          # Environment variable holding the username
    env_pass: MY_REPO_TOKEN          # Environment variable holding the token
```

## Field Reference

| Field | Required | Description |
|---|---|---|
| `url` | yes | Base Artifactory URL (with or without trailing slash). For Conan, this points to the `/api/conan` endpoint. |
| `repository` | yes | Repository name within the Artifactory instance. |
| `type` | no | `generic` (default) or `conan`. |
| `auth` | no | Optional explicit credential mapping. When absent, credentials are looked up via the system keyring under `<user>@<service>` (default behaviour). |

## How Endpoints Are Used

| Where | What for |
|---|---|
| `tool_requires` / `build_requires` entries with `type: artifact` | Download non-Conan artefacts via `ArtifactoryInstaller`. The entry's `artifactory:` key selects an endpoint here. |
| Conan remote setup | Every entry with `type: conan` is registered as a Conan remote during `conan_setup` step. |
| `art_download` action / artefact-fetch steps | Generic file downloads. |
| OSS / SCA / SFA report uploads | Some steps push reports back to the Artifactory; the endpoint is selected by name. |

## Credentials

Default behaviour: credentials are read from the OS keyring (Windows Credential Manager / GNOME Keyring) under `<current-user>@<artifactory-host>`. Manage with:

```powershell
.\build.ps1 creds check
.\build.ps1 creds new --service rb-artifactory.bosch.com --username <user>
.\build.ps1 creds renew
```

To override per-endpoint (e.g. a service account for a specific repo), use the `auth` block with environment-variable names. **Never commit raw passwords** — only `env_*` references are accepted.

## Minimal Example

```yaml
my-repo:
  url: https://artifactory.example.com/artifactory/
  repository: my-repo-local
```

## See Also

- [Requirements files](requirements.md) — `type: artifact` entries reference these endpoints
- [main_conf.yml](main_conf.md) — `ARTIFACTORIES` field
- [Getting Started](../getting_started.md) — `creds` command group
