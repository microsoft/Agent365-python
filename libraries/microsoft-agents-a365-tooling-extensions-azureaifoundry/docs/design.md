# Tooling Extensions - Azure AI Foundry - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-azureaifoundry` package.

## Overview

This extension adapts MCP tool server configurations to Azure AI Foundry, enabling AI agents built with Azure AI Foundry to use MCP tools.

## Key Components

### McpToolRegistrationService

The main service for registering MCP tools with Azure AI Foundry agents.

```python
from microsoft_agents_a365.tooling.extensions.azureaifoundry import McpToolRegistrationService

service = McpToolRegistrationService()

# Register MCP tools with Azure AI Foundry agent
tools = await service.register_tools(
    agent_id=agent_id,
    auth_token=auth_token,
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
McpToolRegistrationService.register_tools()
       │
       ├── Convert to Azure AI Foundry tool format
       └── Return tool definitions
       │
       ▼
Azure AI Foundry Agent with MCP tools
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/azureaifoundry/
├── __init__.py
└── services/
    ├── __init__.py
    └── mcp_tool_registration_service.py
```

## Dependencies

- Azure AI Foundry SDK
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-a365-runtime` - Utility functions
