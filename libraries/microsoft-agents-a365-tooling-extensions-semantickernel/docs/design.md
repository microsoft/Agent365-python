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

## Chat History API

The `McpToolRegistrationService` provides methods to send chat history from Semantic Kernel agents to the MCP platform for real-time threat protection and compliance monitoring.

### send_chat_history

Send chat history from a Semantic Kernel `ChatHistory` object:

```python
from semantic_kernel.contents import ChatHistory
from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService

service = McpToolRegistrationService()

# Create and populate chat history
chat_history = ChatHistory()
chat_history.add_user_message("Hello!")
chat_history.add_assistant_message("Hi there! How can I help you?")
chat_history.add_user_message("Tell me about the weather.")

# Send chat history to MCP platform
result = await service.send_chat_history(
    turn_context=turn_context,
    chat_history=chat_history,
    limit=50,  # Optional: send only the most recent 50 messages
)

if result.succeeded:
    print("Chat history sent successfully")
else:
    print(f"Failed to send chat history: {result.errors}")
```

### send_chat_history_messages

Send a list of `ChatMessageContent` objects directly:

```python
from semantic_kernel.contents import ChatMessageContent, AuthorRole
from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService

service = McpToolRegistrationService()

# Create messages directly
messages = [
    ChatMessageContent(role=AuthorRole.USER, content="Hello!"),
    ChatMessageContent(role=AuthorRole.ASSISTANT, content="Hi there!"),
]

# Send messages to MCP platform
result = await service.send_chat_history_messages(
    turn_context=turn_context,
    messages=messages,
)

if result.succeeded:
    print("Messages sent successfully")
```

### Message Conversion Flow

```
ChatHistory / List[ChatMessageContent]
       │
       ▼
McpToolRegistrationService.send_chat_history()
       │
       ├── Extract messages from ChatHistory
       ├── Apply limit if specified (most recent N)
       │
       ▼
McpToolRegistrationService.send_chat_history_messages()
       │
       ├── Convert ChatMessageContent to ChatHistoryMessage
       │   ├── Map AuthorRole to lowercase string (USER → "user")
       │   ├── Extract content as string
       │   ├── Extract ID from metadata or generate UUID
       │   └── Extract timestamp from metadata or use current UTC
       │
       ├── Filter invalid messages (None, empty content)
       │
       ▼
McpToolServerConfigurationService.send_chat_history()
       │
       ▼
MCP Platform (real-time threat protection)
```

### Error Handling

Both methods return an `OperationResult`:

- `result.succeeded` - Boolean indicating success
- `result.errors` - List of errors if the operation failed

Validation errors (e.g., None turn_context) raise `ValueError` immediately.

## Dependencies

- `semantic-kernel` - Semantic Kernel framework
- `microsoft-agents-a365-tooling` - Core tooling service
- `microsoft-agents-a365-runtime` - Utility functions and OperationResult
