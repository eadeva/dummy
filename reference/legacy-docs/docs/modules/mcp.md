# MCP Servers

**Package:** `xc_ce_utils.mcp`
**Purpose:** Model Context Protocol (MCP) server implementations for AI assistant integration with enterprise systems

## Overview

The `mcp` package provides stdio-based MCP servers that expose Bosch enterprise tools as AI-accessible tool interfaces. Each server can be launched from the CLI and is configured for VS Code via the `vs_code_configurator`.

## Available Servers

| Server | Package | Systems Accessed |
|---|---|---|
| **RTC** | `mcp/rtc/` | IBM Rational Team Concert — work items, queries, state transitions |
| **DNG** | `mcp/dng/` | IBM DOORS Next Generation — requirements, modules, artifacts |
| **Docupedia** | `mcp/docupedia/` | Bosch Confluence (Docupedia) — pages, search, labels |
| **Artifactory** | `mcp/artifactory/` | JFrog Artifactory — package search, download, metadata |
| **DiaBrain** | `mcp/diabrain/` | DiaBrain MCP Servers |

## Architecture

- `registry.py` — `MCPServerEntry` dataclass and `register()` function for server registration
- `config.py` — Loads project-level MCP configuration from YAML
- Each server subdirectory contains its own MCP tool definitions and service client

## Usage

```powershell
# List available servers
python -m xc_ce_utils _mcp --list

# Launch a server (used by VS Code)
python -m xc_ce_utils _mcp rtc
```

## Configuration

MCP servers are configured per-project in `config/copilot/copilot_config.yml` and installed into `.vscode/mcp.json` by `config-devops vs-code regen-mcp-json`.

## See Also

- [VS Code Configurator](vs_code_configurator.md) — sets up MCP server configs
- [RTC Client Wrapper](rtc_client_wrapper.md) — underlying RTC client used by the RTC MCP server
