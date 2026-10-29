# VS Code Configurator

**Package:** `xc_ce_utils.vs_code_configurator`

Manages GitHub Copilot instructions, VS Code tasks, extensions, and MCP server configuration for projects.

---

## Key Components

### `CopilotInstructionsManager`

Copies instruction topics, chat agents, prompt templates, and code templates from xc-ce-utils to the project's `.github/` directory. Generates `copilot-instructions.md` from `copilot_config.yml`.

```python
from xc_ce_utils.vs_code_configurator import CopilotInstructionsManager

manager = CopilotInstructionsManager(
    repo_root=Path.cwd(), config_path=Path("config/copilot/copilot_config.yml")
)
manager.generate_all()
```

### `generate_vscode_commands.py`

Creates `.vscode/tasks.json` with variant x action combinations (build, clean, rebuild per variant).

### `install_vscode_extensions.py`

Installs the recommended VS Code extensions from configuration, on demand via
`./build.ps1 config vs-code refresh-extensions` (not automatically during setup).

### `setup_mcp_servers.py`

Configures MCP (Model Context Protocol) server definitions in VS Code settings for AI-assisted development.

---

## Invocation

```bash
./build.ps1 config vs-code refresh-extensions
./build.ps1 config-devops vs-code regen-ws-conf
./build.ps1 config-devops vs-code regen-copilot
./build.ps1 config-devops vs-code regen-mcp-json
```

Run only the subcommands you need:
1. `refresh-extensions`: install/update local VS Code extensions
2. `regen-ws-conf`: regenerate committed workspace VS Code settings/tasks/extensions
3. `regen-copilot`: regenerate committed Copilot instruction artifacts
4. `regen-mcp-json`: regenerate committed MCP server configuration

---

## Configuration

Driven by `config/copilot/copilot_config.yml`:

```yaml
enabled: true
instruction_topics:
  - filename: python_best_practices.instructions.md
    enabled: true
chatmodes:
  - filename: beastmode-copilot.agent.md
    enabled: true
generate_xc_ce_utils_doc:
  enabled: true
```

---

## See Also

- [Git Hooks](git_hooks.md) — hook installation via `config refresh-hooks`
