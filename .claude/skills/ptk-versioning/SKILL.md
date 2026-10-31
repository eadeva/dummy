---
name: ptk-versioning
description: Configure PTK project and component version discovery, Git tag patterns, variant release lines, VMR version dependencies and generated version headers or build-system files. Use when versions must be discovered and exposed to job steps without bumping or tagging.
---

# PTK version discovery

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [versioning](../../../docs/guides/versioning.rst), the discovered repository alias and existing version/variant configuration. Git, variants and independently versioned components are not mandatory. Put maintained rules in `versioning.ptk.yml` under `repository.config_path`, using the versioning body without a root wrapper.
2. Choose the actual source: Git, a repository file, caller environment, literal or read-only command. For Git, confirm reachable tags, the glob, prefix, history depth and dirty policy. Do not choose the highest tag anywhere in the repository or silently replace a missing source with a fabricated version.
3. Let components inherit the project version unless independently versioned. Use explicit variant source overrides for existing divergent release lines. For VMR dependencies, name the repository alias and dependent variant deliberately.
4. Preview the selected job and inspect `ptk maintainer version --help` for discovery commands. Generated `.gen.version.ptk.yml` files are output snapshots: ignore them in Git and never include them as maintained configuration. Custom command sources may execute even during previews; keep them read-only.
5. Use `PTK_VERSION_ALIAS` for a project and `PTK_VERSION_ALIAS_COMPONENT_NAME` for a component. Prefer documented `${version.projects.alias...}` fields or `version.generate` for headers/build-system values. Read the supported generator fields from the versioning reference; do not infer names.
6. Verify the generated version file and the consuming build command against the same run snapshot. Record fallback use and dirty/shallow status. Never add a version bump, commit or tag operation to discovery.
7. For Python distribution metadata, follow [package preparation](../../../docs/guides/packaging.rst) and validate PEP 440 compatibility. Preserve the version frozen into an sdist when rebuilding it elsewhere.

For native GitHub pipelines, matrix setup freezes producer version/commit and artifact destinations before execution. Ensure checkout supplies the needed tags/history and preserve that identity through upload/download; do not recompute dated destinations independently in consumers. See [GitHub workflows](../ptk-github-workflows/SKILL.md).
