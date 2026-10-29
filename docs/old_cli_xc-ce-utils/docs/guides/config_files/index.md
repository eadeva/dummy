# Configuration File Reference

Detailed per-file references for every YAML/JSON configuration file consumed by XC-CE Utils. These pages complement the high-level [Configuration Guide](../config_guide.md).

```{toctree}
:maxdepth: 1
:caption: Per-File References

main_conf
project_conf
actions_conf
action_file
requirements
artifactory_conf
versioning
cx_conf
oss_conf
env_isolation
```

## Quick Index

| File | Purpose |
|---|---|
| [main_conf.yml](main_conf.md) | Top-level entry point; chains all other configs via file references |
| [project_conf.yml](project_conf.md) | Project identity, global defaults, variant matrix |
| [actions_conf.yml](actions_conf.md) | Action registry mapping names → action files |
| [Action files](action_file.md) | Anatomy of `build.yml`, `doc.yml`, `sca.yml`, … |
| [Requirements files](requirements.md) | `tool_requires` / `build_requires` / `test_requires` — Conan, Artifactory, Toolbase |
| [artifactory_conf.yml](artifactory_conf.md) | Artifactory endpoint definitions |
| [versioning/version.json](versioning.md) | Semantic version fields (`RB_VERSIONING`) — static file or `git-managed` mode |
| [cx/cx_conf.yml](cx_conf.md) | CI-specific configuration and overrides |
| [oss/oss_conf.yml](oss_conf.md) | Open-source scanning configuration |
| [env/env_isolation.yml](env_isolation.md) | Environment-variable isolation rules |
