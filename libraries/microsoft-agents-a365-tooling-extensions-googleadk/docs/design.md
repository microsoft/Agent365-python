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
       ├── Remove MCP toolsets attached by an earlier call
       ├── Exchange token for MCP scope
       ├── Create McpToolset for each server
       └── Modify agent in place to add all tools
       │
       ▼
Google ADK Agent with MCP tools
```

### Reusing an agent across turns

Each `McpToolset` carries the Authorization token of the turn it was created for. On every call,
`add_tool_servers_to_agent` first removes the toolsets an earlier call added (tracked by object
identity, across service instances) and closes them in the background, then creates toolsets for
the current turn; `cleanup()` waits for those closes to finish. An agent that is reused from one
turn to the next does not keep toolsets that carry an earlier turn's headers, even if the call
fails, and does not accumulate open MCP sessions. Tools you add to the agent yourself are kept
as-is. Because the agent is modified in place, turns that run concurrently must each use their own
agent, for example a `clone()` of a base agent.

### Per-turn usage

```python
service = McpToolRegistrationService()
agent = base_agent.clone()
try:
    await service.add_tool_servers_to_agent(agent, auth, "agentic", turn_context)
    async for event in Runner(app_name=app_name, agent=agent, session_service=sessions).run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        ...
finally:
    await service.cleanup()
```

One agent must not be shared by turns that run at the same time: each call replaces the agent's
toolsets and closes the ones it replaces, which ends any other turn that is still using them.
`cleanup()` closes every toolset the service created, so use a separate service for each turn. A
long-lived service can serve concurrent turns as long as each turn has its own agent and `cleanup()`
isn't called while other turns still run; the toolsets are then closed when each turn's agent is
garbage collected, as described next.

### Closing toolsets when their agent is garbage collected

If `cleanup()` isn't called, the sessions are still bounded by the agents that use them. Each
toolset is recorded against the agent it was added to, together with the event loop it was added
on, and a `weakref.finalize` callback on that agent closes the agent's toolsets once it is garbage
collected. Because garbage collection can run in any thread, the callback only uses
`loop.call_soon_threadsafe` to close them on that loop with `McpToolset.close()`, in a background
task, and it does nothing if that loop is already closed. ADK runs each MCP session in a task of its
own and closes it on the loop it was created on, so closing from that task is safe. A toolset that a
later call replaces is removed from its agent's record when it is closed. A toolset is only ever
added to one agent, so it is closed when that agent is collected. Closed toolsets are also dropped
from the service's tracking. `cleanup()` is still the deterministic way to close them, and closing a
toolset twice has no effect, so the two paths don't conflict.

The finalizer holds the toolsets, not the agent, so it doesn't keep the agent alive; an `McpToolset`
doesn't refer to its agent either. `clone()` copies the agent's tool list, so a clone made after
this call holds the same toolsets without keeping them open, and ADK reconnects a closed toolset
the next time it is used. Clone the base agent before calling `add_tool_servers_to_agent`, not
after.

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
