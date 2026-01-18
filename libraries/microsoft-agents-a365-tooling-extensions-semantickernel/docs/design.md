# Tooling Extensions - Semantic Kernel - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-semantickernel` package.

## Overview

This extension adapts MCP tool server configurations to Semantic Kernel plugins, enabling Semantic Kernel-based agents to use MCP tools.

## Key Components

### McpToolRegistrationService

The main service for registering MCP tools as Semantic Kernel plugins.

```python
from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService

service = McpToolRegistrationService()

# Get MCP tools as Semantic Kernel plugins
plugins = await service.get_plugins(
    kernel=kernel,
    agent_id=agent_id,
    auth_token=auth_token,
)

# Add plugins to kernel
for plugin in plugins:
    kernel.add_plugin(plugin)
```

### Integration Flow

```
McpToolServerConfigurationService
       │
       ▼
List MCPServerConfig objects
       │
       ▼
McpToolRegistrationService.get_plugins()
       │
       ├── Discover available tools from MCP servers
       ├── Convert to Semantic Kernel plugin format
       └── Return plugin objects
       │
       ▼
Semantic Kernel with MCP plugins
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/semantickernel/
├── __init__.py
└── services/
    ├── __init__.py
    └── mcp_tool_registration_service.py
```

## Dependencies

- `semantic-kernel` - Semantic Kernel framework
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-a365-runtime` - Utility functions
