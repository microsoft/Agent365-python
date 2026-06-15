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
       ├── Gate (per server, non-blocking): Ready → MCPStreamableHTTPTool; Pending → placeholder tool
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

### Connection-readiness gating (non-blocking, per server)

MCP server discovery runs every turn. The gateway reports each server's `connectivityStatus`
(`"Ready"` or `"Pending"`) along with a `missingConnectionsUrl` the user can visit to set up the
connection(s) that server needs. Gating is **per server and non-blocking**:

- A **Ready** server (or a legacy source with no `connectivityStatus`) is wired as a live
  `MCPStreamableHTTPTool`, exactly as before.
- A **Pending** server is wired as a single **placeholder tool** named after the server. The agent
  is still built and the Ready servers remain fully usable for the turn. Only if the model invokes
  the placeholder — because the user's request actually needs that server — does it return a static
  message (including `missingConnectionsUrl`) for the model to relay to the user. If the turn never
  needs the Pending server, the user is never bothered. A later turn re-runs discovery and wires the
  server for real once its connections are in place.

The placeholder **returns** the message rather than raising it. Agent Framework's tool-call loop
catches exceptions raised inside a `FunctionTool` and reflects them to the model as an opaque error
string (`"Error: Function failed."` by default), and it converts `UserInputRequiredException` into
tool-result content rather than propagating it — so returning the text is the only way to surface
the setup URL through the model. Because surfacing flows through the model, exact verbatim delivery
is best-effort; the placeholder's description instructs the model to relay the message and URL
verbatim, and `max_invocations=1` stops the model from looping on it within a turn.

> **Note:** A Pending server is represented by one placeholder named after the server (its real
> sub-tools are invisible until it connects). The model routes the user's intent to it by server
> name plus description — best-effort, not guaranteed.

```python
from microsoft_agents_a365.tooling.extensions.agentframework import (
    McpToolRegistrationService,
)

service = McpToolRegistrationService()

# Non-blocking: Pending servers become placeholders, so no special handling is needed in the
# turn handler. The agent is always built and Ready tools always run.
agent = await service.add_tool_servers_to_agent(
    chat_client=chat_client,
    agent_instructions="You are a helpful assistant.",
    initial_tools=[],
    auth=auth_context,
    auth_handler_name="graph",
    turn_context=turn_context,
)
```

For developers who instead want **blocking** behavior (abort the whole turn until every server is
connected), the extension still exports `McpConnectionsRequiredError`. Inspect the discovered
servers yourself and raise it before building the agent:

```python
from microsoft_agents_a365.tooling.extensions.agentframework import McpConnectionsRequiredError
```

`McpConnectionsRequiredError` exposes `missing_connections_url`, `connectivity_status`, and
`server_names`, and its message is built from the same `format_mcp_connections_required_message`
helper the placeholder uses. It is owned and exported by this extension
(`microsoft_agents_a365.tooling` core only parses the per-server connection metadata; it never
gates or raises).

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
