# Tooling Extensions - OpenAI - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-openai` package.

## Overview

This extension adapts MCP tool server configurations to OpenAI's function calling interface, enabling OpenAI-based agents to use MCP tools.

## Key Components

### McpToolRegistrationService

The main service for registering MCP tools with OpenAI function calling.

```python
from microsoft_agents_a365.tooling.extensions.openai import McpToolRegistrationService

service = McpToolRegistrationService()

# Get MCP tools as OpenAI function definitions
functions = await service.get_function_definitions(
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
McpToolRegistrationService.get_function_definitions()
       │
       ├── Discover available tools from MCP servers
       ├── Convert to OpenAI function schema format
       └── Return function definitions
       │
       ▼
OpenAI API with function calling
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/openai/
├── __init__.py
└── mcp_tool_registration_service.py
```

## Dependencies

- `openai` - OpenAI SDK
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-a365-runtime` - Utility functions
