# Tooling Extensions - Google ADK - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-googleadk` package.

## Overview

This extension adapts MCP tool server configurations to Google's Agent Development Kit (ADK), enabling Google ADK-based agents to use MCP tools through the `McpToolset` interface.

## Key Components

### McpToolRegistrationService

The main service for registering MCP tools with Google ADK agents.

```python
from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

service = McpToolRegistrationService()

# Add MCP tools to existing agent (modified in place)
await service.add_tool_servers_to_agent(
    agent=existing_agent,
    auth=auth_context,
    auth_handler_name="graph",
    context=turn_context,
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
       ├── Exchange token for MCP scope
       ├── Create McpToolset for each server
       └── Modify agent in place to add all tools
       │
       ▼
Google ADK Agent with MCP tools
```

### add_tool_servers_to_agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent` | `Agent` | The existing Google ADK agent |
| `auth` | `Authorization` | Auth context for token exchange |
| `auth_handler_name` | `str` | Name of auth handler |
| `context` | `TurnContext` | Conversation context |
| `auth_token` | `str \| None` | Optional pre-obtained token |

### McpToolset Creation

For each MCP server configuration:

```python
server_info = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=config.url,
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
)
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/googleadk/
├── __init__.py
└── services/
    ├── __init__.py
    └── mcp_tool_registration_service.py
```

## Dependencies

- `google-adk` - Google Agent Development Kit
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-hosting-core` - Authorization and TurnContext
