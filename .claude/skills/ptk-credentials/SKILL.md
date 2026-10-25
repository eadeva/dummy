---
name: ptk-credentials
description: Declare, provision or troubleshoot ptk credentials without exposing secret
  values.
---

# ptk-credentials

1. Read [docs/configuration.rst](../../../docs/configuration.rst) and [docs/cli.rst](../../../docs/cli.rst); inspect the credential fields with `ptk setup config schema`.

2. Declare fields and an ordered provider chain; default order is env, keyring, gopass, vault, prompt.

3. Diagnose using `ptk setup creds setup` and `ptk setup creds list NAME`. Use `ptk setup creds set NAME FIELD --store vault` for hidden input when appropriate.

4. Map secrets into individual step environment variables with `secrets: {TOKEN: service.token}`.

5. Have child programs read their environment directly. Shell expansion into curl or other command arguments still exposes secrets in process listings.

6. Never put values in YAML, command arguments, generated docs, test snapshots or commit messages.

7. Use synthetic credentials in tests. Verify skipped steps need no credentials and dry runs do not retrieve them.

8. Check masking in logs/events/reports for real execution; short secrets have masking limitations.

9. In CI, provide the declared env variables and avoid interactive prompt providers. Store only through a provider that supports writes.

10. Use `creds test NAME` only after inspecting the configured test command and its external effects.

In VMR mode, use `ptk setup creds list` for shared names and repository-qualified conflicts. Listing must never unlock a store. Use the storage namespace when implementing providers; logical credential references alone are not unique across VMR definitions.
