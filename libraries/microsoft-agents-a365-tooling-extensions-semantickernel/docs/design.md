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

### Reusing a kernel across turns

`add_tool_servers_to_agent` adds one MCP plugin per server, carrying the Authorization token of the
current turn. On every call it first removes the plugins an earlier call added, including copies
made by `Kernel.clone()` (tracked by object identity, across service instances). A kernel that is
reused from one turn to the next does not keep a plugin that carries an earlier turn's headers, even
when a server is not rediscovered or fails to connect. Plugins you add to the kernel yourself are
kept as-is. Because the kernel is modified in place, turns that run concurrently must each use their
own kernel, for example a `clone()` of a base kernel without these plugins.

The `MCPStreamableHttpPlugin` behind each removed plugin is closed in a background task and is no
longer tracked by the service, so a reused kernel keeps only the current turn's connections open.
The plugin is found through the functions of the removed kernel plugin (or, for a server without
tools or prompts, through the kernel plugin it was added as), so plugins that `Kernel.clone()`
copies share are closed too; they carry the headers of the earlier turn. `MCPPluginBase.close()`
only signals the plugin's own connection task and waits for it, so it is safe to call from any task.
`cleanup_connections()` waits for these closes to finish.

`MCPPluginBase.connect()` waits for its background connection task to report that it is ready. When
a server rejects the session (for example with HTTP 403), that task can end without reporting, so
the service also watches the task and skips the server instead of waiting forever. When the
transport can't be created, the task reports ready and then fails, so `connect()` returns without a
connection; the service skips that server too. If the call is cancelled while a server is still
connecting, the background task keeps connecting, so the service closes the plugin once that task
is done. The task is the private `MCPPluginBase._current_task`. Tests on a real
`MCPStreamableHttpPlugin` fail if a Semantic Kernel version stops setting it, and at run time the
service logs a warning (once per process) when a plugin that is still connecting doesn't have it.
A plugin that connects but that `Kernel.add_plugin()` then rejects, for example because the server
name isn't a valid plugin name, is closed too.

### Per-turn usage

```python
service = McpToolRegistrationService()
kernel = base_kernel.clone()
try:
    await service.add_tool_servers_to_agent(kernel, auth, "agentic", turn_context)
    result = await kernel.invoke_prompt(user_message)
finally:
    await service.cleanup_connections()
```

One kernel, or `Kernel.clone()` copies of a kernel that the service added plugins to, must not be
shared by turns that run at the same time: each call replaces those plugins and closes the ones it
replaces, which ends any other turn that is still using them. `cleanup_connections()` closes every
plugin the service connected, so use a separate service for each turn. A long-lived service can
serve concurrent turns as long as each turn has its own kernel and `cleanup_connections()` isn't
called while other turns still run; the plugins are then closed when each turn's kernel is garbage
collected, as described next.

### Closing plugins when their kernel is garbage collected

If `cleanup_connections()` isn't called, the connections are still bounded by the kernels that use
them. Each plugin is recorded against the kernel it was added to, together with the event loop it
connected on, and a `weakref.finalize` callback on that kernel closes the kernel's plugins once it
is garbage collected. Because garbage collection can run in any thread, the callback only uses
`loop.call_soon_threadsafe` to close each plugin on its own loop, in a background task, and it does
nothing if that loop is already closed. A plugin that a later call replaces is removed from its
kernel's record when it is closed, so a reused kernel doesn't accumulate closed plugins. A plugin is
only ever added to one kernel, so it is closed when that kernel is collected. Closed plugins are also
dropped from the service's tracking, on each call and when their kernel is collected.
`cleanup_connections()` is still the deterministic way to close them, and closing a plugin twice
has no effect, so the two paths don't conflict.

`Kernel.add_plugin()` stores the kernel on the plugin (`MCPPluginBase.added_to_kernel`), and a
connected plugin is kept alive by its own connection task, so it would keep the kernel alive and
the kernel would never be collected. The service replaces that reference with a `weakref.proxy` to
the kernel, so the plugin can still use the kernel while it exists, for example for sampling. A test
on a real `MCPStreamableHttpPlugin` fails if a Semantic Kernel version keeps the kernel some other
way.

A `Kernel.clone()` copy shares the plugins' functions but doesn't keep the plugins open, and the
same goes for any other kernel these plugins or functions are copied into. Don't keep using such a
copy after the kernel that the service added the plugins to is gone.

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
