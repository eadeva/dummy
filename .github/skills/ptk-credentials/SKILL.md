---
name: ptk-credentials
description: Declare, provision or diagnose credential providers and step secret injection in a PTk project. Use for missing credentials, provider conflicts and requested setup without exposing values or retrieving secrets merely to inspect availability.
---

# ptk-credentials

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [docs/guides/configuration.rst](../../../docs/guides/configuration.rst) and [docs/reference/cli.rst](../../../docs/reference/cli.rst); inspect the credential fields with `ptk describe --json --configuration` (or the bundled schema when runtime inspection is unavailable).

2. Declare fields and an optional ordered `providers` chain; default and only providers are env, vault, prompt. env reads the `env` field mapping, else `<PROJECT>_<USER>_<CREDENTIAL>_<FIELD>` (any user ID in CX), else `PTK_CRED_<CREDENTIAL>_<FIELD>`. Prompted values are stored in the vault unless `remember: false`.

3. Start with `ptk self-service creds list NAME` to inspect declared provider availability without unlocking a store. Use `setup` (creates the encrypted per-user vault when missing, except in CX) or `set NAME FIELD --store PROVIDER` only for requested provisioning.

4. After the master password, the vault stays unlocked for `PTK_VAULT_UNLOCK_HOURS` (default 8; `0` asks every run); `PTK_VAULT_PASSWORD` keeps no session. `creds lock` ends the session. `creds reset [--yes]` deletes the vault and every secret in it; run it only when the user explicitly asks (e.g. forgotten master password).

5. Map secrets into individual step environment variables with `secrets: {TOKEN: service.token}`.

6. Have child programs read their environment directly. Shell expansion into curl or other command arguments still exposes secrets in process listings.

7. Never put values in YAML, command arguments, generated docs, test snapshots or commit messages.

8. Use synthetic credentials in tests. Verify skipped steps need no credentials and dry runs do not retrieve them.

9. Review masking using synthetic values. Do not print or retrieve real secrets to test masking; short secrets have masking limitations.

10. For native GitHub artifact Actions, pass technical-user and token through workflow secret references. Their curl runtime uses stdin for credentials; do not replace it with interpolated command-line authentication. Keep `additional_properties` free of secrets. See [GitHub workflows](../ptk-github-workflows/SKILL.md).

11. In CX, provide the declared env variables; prompting is unavailable there. Only the vault stores values.

12. Use `ptk self-service creds test NAME` only after inspecting the configured test command and its external effects.

In VMR mode, use `ptk self-service creds list` for shared names and repository-qualified conflicts. Listing must never unlock a store. Preserve the owning repository and configured storage namespace when diagnosing conflicts; logical names alone are not unique across VMR definitions. Use supported providers or ordinary external tools, not an invented provider plugin.
