---
name: ptk-package-preparation
description: "Prepare and verify a consuming project\u2019s package artifacts using its existing build backend and version source. Use for declared outputs, wheel/sdist checks and release handoff without implicit publishing; distinguish PTk\u2019s own packaging checkout explicitly."
---

# PTk package preparation

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

For the destination stage, read [Artifactory destinations](../../../docs/guides/artifacts.rst). `ptk maintainer artifacts destination --job JOB --format github` emits URL/repository/path only. Keep file selection, authentication and uploads in GitHub workflows. Use `${version.current.sort_key}_v${version.current.value}` for numeric release folders, `${version.current.build_label}` for per-build subfolders, and `${date.timestamp}` or `${date.utc.timestamp}` for dated paths. Event routes accept a list of branch globs. The numeric sort key does not order prerelease labels. Select the actual packaging job; a job named `package` is not required.

1. Read [package preparation](../../../docs/guides/packaging.rst) and the project's existing package job/backend. Distinguish PTk's own `package` job and helper script from an arbitrary consumer repository; do not assume those files exist there.
2. Confirm where the version is discovered. For a PTk source checkout, inspect its configured version source and build metadata hook. For another project, wire its own backend to its declared version source rather than copying a static version. Do not create tags or publish as part of preparation.
3. Declare prepared outputs and optional artifact types explicitly on the producing step/job; do not opt into cache implicitly. For a requested upload/download pipeline use [GitHub workflows](../ptk-github-workflows/SKILL.md). Inspect the exact completed `upload.json` and run-job outputs; setup does not know runtime paths.
4. For Python projects, keep build dependencies in the project's existing dependency groups or selected environment; do not add pyproject.toml to a non-Python project merely to use PTk. Use PTk's existing Python-step support to invoke the build backend. Stage artifacts separately and preserve prior validated output if a new build fails.
5. Validate sdist and wheel metadata and package contents; build the wheel from the sdist and smoke-test installation outside the source checkout. Check the reported version matches the prepared snapshot. Include hashes and a manifest when implementing an artifact handoff.
6. Ship lightweight offline reference material and project-facing skills when required. Keep full rendered documentation a separate artifact and Sphinx out of runtime dependencies. Do not include local credentials, caches, generated version snapshots or test logs in distributions.
7. When packaging PTk itself, validate `ptk maintainer sync agent` from an installed wheel in a disposable consumer project. An unrelated Python package need not bundle PTk agents or the VSIX. Check rewritten documentation links without relying on PTk's source checkout. Preserve locally modified managed files through the installer's normal conflict checks; `--force` requires the maintainer's interactive confirmation.
8. Report artifact paths, version, validation and limitations. Preparing for Artifactory does not authorize uploading, changing credentials, publishing a release or creating tags.
