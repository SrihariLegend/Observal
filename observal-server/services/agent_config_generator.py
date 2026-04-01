from models.agent import Agent
from services.config_generator import generate_config


def generate_agent_config(agent: Agent, ide: str) -> dict:
    """Generate IDE-specific config for an agent, bundling prompt + MCP configs."""
    mcp_configs = {}

    # Registry MCPs
    for link in agent.mcp_links:
        listing = link.mcp_listing
        cfg = generate_config(listing, ide)
        if ide == "claude-code":
            mcp_configs[listing.name] = cfg
        elif "mcpServers" in cfg:
            mcp_configs.update(cfg["mcpServers"])

    # External MCPs
    for ext in (agent.external_mcps or []):
        name = ext.get("name", "")
        if not name:
            continue
        if ide == "claude-code":
            args_str = " ".join(ext.get("args", []))
            mcp_configs[name] = {"command": f"claude mcp add {name} -- {ext.get('command', 'npx')} {args_str}".strip(), "type": "shell_command"}
        elif ide == "gemini-cli":
            mcp_configs[name] = {"command": ext.get("command", "npx"), "args": ext.get("args", [])}
        else:
            mcp_configs[name] = {"command": ext.get("command", "npx"), "args": ext.get("args", []), "env": ext.get("env", {})}

    if ide == "claude-code":
        setup_commands = [c.get("command", "") for c in mcp_configs.values() if isinstance(c, dict) and c.get("type") == "shell_command"]
        return {
            "rules_file": {"path": f".claude/rules/{agent.name}.md", "content": agent.prompt},
            "mcp_setup_commands": setup_commands,
        }

    if ide == "kiro":
        return {
            "rules_file": {"path": f".kiro/rules/{agent.name}.md", "content": agent.prompt},
            "mcp_json": {"mcpServers": mcp_configs},
        }

    if ide == "gemini-cli":
        return {
            "rules_file": {"path": "GEMINI.md", "content": agent.prompt},
            "mcp_config": {"mcpServers": mcp_configs},
        }

    # Default (cursor, vscode, windsurf)
    return {
        "rules_file": {"path": f".rules/{agent.name}.md", "content": agent.prompt},
        "mcp_config": {"mcpServers": mcp_configs},
    }
