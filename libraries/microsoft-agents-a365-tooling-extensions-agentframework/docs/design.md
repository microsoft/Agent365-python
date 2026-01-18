# Tooling Extensions - Agent Framework - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-agentframework` package.

## Overview

This extension adapts MCP tool server configurations to the Microsoft Agents SDK (Agent Framework), enabling agents to use MCP tools through the `MCPStreamableHTTPTool` interface.

## Key Components

### McpToolRegistrationService

The main service for registering MCP tools with Agent Framework agents.

```python
from microsoft_agents_a365.tooling.extensions.agentframework import McpToolRegistrationService

service = McpToolRegistrationService()

# Create agent with MCP tools
agent = await service.add_tool_servers_to_agent(
    chat_client=azure_openai_client,
    agent_instructions="You are a helpful assistant.",
    initial_tools=[],
    auth=auth_context,
    auth_handler_name="graph",
    turn_context=turn_context,
)
```

### Integration Flow

```
McpToolServerConfigurationService
       │
       ▼
List MCPServerConfig objects
       │
       ▼
McpToolRegistrationService.add_tool_servers_to_agent()
       │
       ├── Resolve agent identity
       ├── Exchange token for MCP scope
       ├── Create MCPStreamableHTTPTool for each server
       └── Create ChatAgent with all tools
       │
       ▼
ChatAgent with MCP tools
```

### add_tool_servers_to_agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `chat_client` | `OpenAIChatClient \| AzureOpenAIChatClient` | The LLM client |
| `agent_instructions` | `str` | Agent behavior instructions |
| `initial_tools` | `List[Any]` | Non-MCP tools to include |
| `auth` | `Authorization` | Auth context for token exchange |
| `auth_handler_name` | `str` | Name of auth handler |
| `turn_context` | `TurnContext` | Conversation context |
| `auth_token` | `str \| None` | Optional pre-obtained token |

### MCPStreamableHTTPTool Creation

For each MCP server configuration:

```python
mcp_tool = MCPStreamableHTTPTool(
    name=config.mcp_server_name,
    url=config.mcp_server_unique_name,
    headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "Agent365SDK/..."
    },
    description=f"MCP tools from {config.mcp_server_name}"
)
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/agentframework/
├── __init__.py
└── services/
    ├── __init__.py
    └── mcp_tool_registration_service.py
```

## Dependencies

- `agent-framework-azure-ai` - Microsoft Agents SDK
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-a365-runtime` - Utility functions
