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

### Chat History API

The service provides methods to send chat history to the MCP platform for real-time threat protection analysis. This enables security scanning of conversation content.

#### send_chat_history_messages

The primary method for sending chat history. Converts Agent Framework `ChatMessage` objects to the `ChatHistoryMessage` format expected by the MCP platform.

```python
from agent_framework import ChatMessage, Role

service = McpToolRegistrationService()

# Create messages
messages = [
    ChatMessage(role=Role.USER, text="Hello, how are you?"),
    ChatMessage(role=Role.ASSISTANT, text="I'm doing well, thank you!"),
]

# Send to MCP platform for threat protection
result = await service.send_chat_history_messages(messages, turn_context)

if result.succeeded:
    print("Chat history sent successfully")
else:
    print(f"Failed: {result.errors}")
```

#### send_chat_history_from_store

A convenience method that extracts messages from a `ChatMessageStoreProtocol` and delegates to `send_chat_history_messages`.

```python
# Using a ChatMessageStore directly
result = await service.send_chat_history_from_store(
    thread.chat_message_store,
    turn_context
)
```

#### Chat History API Parameters

| Method | Parameter | Type | Description |
|--------|-----------|------|-------------|
| `send_chat_history_messages` | `chat_messages` | `Sequence[ChatMessage]` | Messages to send |
| | `turn_context` | `TurnContext` | Conversation context |
| | `tool_options` | `ToolOptions \| None` | Optional configuration |
| `send_chat_history_from_store` | `chat_message_store` | `ChatMessageStoreProtocol` | Message store |
| | `turn_context` | `TurnContext` | Conversation context |
| | `tool_options` | `ToolOptions \| None` | Optional configuration |

#### Chat History Integration Flow

```
Agent Framework ChatMessage objects
       │
       ▼
McpToolRegistrationService.send_chat_history_messages()
       │
       ├── Convert ChatMessage → ChatHistoryMessage
       │   ├── Extract role via .value property
       │   ├── Generate UUID if message_id is None
       │   ├── Filter out empty/whitespace content
       │   └── Filter out None roles
       │
       ▼
McpToolServerConfigurationService.send_chat_history()
       │
       ▼
MCP Platform Real-Time Threat Protection Endpoint
```

#### Message Filtering Behavior

The conversion process filters out invalid messages:
- Messages with `None` role are skipped (logged at WARNING level)
- Messages with empty or whitespace-only content are skipped
- If all messages are filtered out, the method returns success without calling the backend

This ensures only valid, meaningful messages are sent for threat analysis.

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
