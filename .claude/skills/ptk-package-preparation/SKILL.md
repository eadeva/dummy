---
name: ptk-package-preparation
description: Prepare and validate PTK or project Python package artifacts for a later Artifactory release without publishing, including Git-managed versions, wheels/sdists, documentation and bundled offline authoring resources.
---

# PTK package preparation

First follow the [project discovery and execution guide](../../../docs/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

For the destination stage, read [Artifactory destinations](../../../docs/artifacts.rst). `ptk maintainer artifacts destination --job JOB --format github` emits URL/repository/path only. Keep file selection, authentication and uploads in GitHub workflows. Use `${version.current.sort_key}_v${version.current.value}` for numeric release folders and `${date.timestamp}` or `${date.utc.timestamp}` for dated paths. The numeric sort key does not order prerelease labels. Select the actual packaging job; a job named `package` is not required.

1. Read [package preparation](../../../docs/packaging.rst) and the project's existing package job/backend. Distinguish PTK's own `package` job and helper script from an arbitrary consumer repository; do not assume those files exist there.
2. Confirm where the version is discovered. For a PTK source checkout, inspect its configured version source and build metadata hook. For another project, wire its own backend to its declared version source rather than copying a static version. Do not create tags or publish as part of preparation.
3. Keep build dependencies in the project's Python dependency groups. Use PTK's existing Python-step support to invoke the build backend. Stage artifacts separately and preserve prior validated output if a new build fails.
4. Validate sdist and wheel metadata and package contents; build the wheel from the sdist and smoke-test installation outside the source checkout. Check the reported version matches the prepared snapshot. Include hashes and a manifest when implementing an artifact handoff.
5. Ship lightweight offline reference material and project-facing skills when required. Keep full rendered documentation a separate artifact and Sphinx out of runtime dependencies. Do not include local credentials, caches, generated version snapshots or test logs in distributions.
6. When packaging PTK itself, validate `ptk maintainer sync agent` from an installed wheel in a disposable consumer project. An unrelated Python package need not bundle PTK agents or the VSIX. Check rewritten documentation links without relying on PTK's source checkout. Preserve locally modified managed files through the installer's normal conflict checks.
7. Report artifact paths, version, validation and limitations. Preparing for Artifactory does not authorize uploading, changing credentials, publishing a release or creating tags.
