---
name: ptk-credentials
description: Declare, provision or troubleshoot ptk credentials without exposing secret
  values.
---

# ptk-credentials

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [docs/guides/configuration.rst](../../../docs/guides/configuration.rst) and [docs/reference/cli.rst](../../../docs/reference/cli.rst); inspect the credential fields with `ptk maintainer config schema`.

2. Declare fields and an ordered provider chain; default order is env, keyring, gopass, vault, prompt.

3. Start with `ptk self-service creds list NAME` to inspect declared provider availability without unlocking a store. Use `setup` or `set NAME FIELD --store PROVIDER` only for requested provisioning, selecting a configured writable provider; do not assume vault is available.

4. Map secrets into individual step environment variables with `secrets: {TOKEN: service.token}`.

5. Have child programs read their environment directly. Shell expansion into curl or other command arguments still exposes secrets in process listings.

6. Never put values in YAML, command arguments, generated docs, test snapshots or commit messages.

7. Use synthetic credentials in tests. Verify skipped steps need no credentials and dry runs do not retrieve them.

8. Review masking using synthetic values. Do not print or retrieve real secrets to test masking; short secrets have masking limitations.

9. For native GitHub artifact Actions, pass technical-user and token through workflow secret references. Their curl runtime uses stdin for credentials; do not replace it with interpolated command-line authentication. Keep `additional_properties` free of secrets. See [GitHub workflows](../ptk-github-workflows/SKILL.md).

10. In CX, provide the declared env variables and avoid interactive prompt providers. Store only through a provider that supports writes.

11. Use `ptk self-service creds test NAME` only after inspecting the configured test command and its external effects.

In VMR mode, use `ptk self-service creds list` for shared names and repository-qualified conflicts. Listing must never unlock a store. Use the storage namespace when implementing providers; logical credential references alone are not unique across VMR definitions.
