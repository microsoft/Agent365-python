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

### Adding MCP servers to an agent

```python
agent = await service.add_tool_servers_to_agent(
    agent=base_agent,
    auth=auth,
    auth_handler_name="agentic",
    context=turn_context,
)
```

Each MCP server carries the Authorization token of the turn it was connected for. A server that an
earlier call attached (tracked by object identity, across service instances) is reused only when it
is still connected and its URL and headers, including the token, are identical to the current
turn's. Every other server from an earlier call is closed, including when the call fails or is
cancelled, so an agent from an earlier turn can no longer call MCP servers with that turn's token.
Servers this call connected are also closed if it fails or is cancelled. Servers you configure on
the agent yourself are kept as-is, and the returned agent is a `clone()` of the one passed in, so
its other settings are preserved. When the call fails or is cancelled, the servers it closed are
also removed from the agent passed in, by assigning it a new `mcp_servers` list (clones made with
`clone()` share the old list, which is left unchanged), so that agent can still run without them.

Each server the service creates connects and disconnects in a task of its own. The MCP client keeps
anyio task groups open while it is connected, and closing them from a different task, or a request
failing inside them, would otherwise cancel the task that connected. As a result, any task can close
a server without cancelling a turn that is still using it (that turn's MCP calls fail instead), and
a server that rejects the connection, for example with HTTP 403, is skipped while the remaining
servers are still added.

Build the agent for each turn from a base agent without these servers, use the returned agent only
for that turn, and call `cleanup_all_servers()` when the turn ends. `cleanup_all_servers()` closes
the servers on every agent the service returned, so use a separate service for each turn. Turns
that run concurrently must not share an agent.

#### Per-turn usage

```python
service = McpToolRegistrationService()
agent = await service.add_tool_servers_to_agent(base_agent, auth, "agentic", turn_context)
try:
    result = await Runner.run(agent, user_message)
finally:
    await service.cleanup_all_servers()
```

An agent that `add_tool_servers_to_agent` returned, or clones of it, must not be shared by turns
that run at the same time: each call closes the servers it replaces, which ends any other turn that
is still using them. A long-lived service can serve concurrent turns as long as each turn has its
own agent and the service's `cleanup_all_servers()` isn't called while other turns still run; in
that case the servers are closed when each turn's agent is garbage collected, as described next.

#### Closing servers when their agent is garbage collected

If `cleanup_all_servers()` isn't called, the connections are still bounded by the agents that use
them. The returned agent gets its `mcp_servers` as a list type of the service's own, which supports
weak references; `clone()` shares that list unless it is given new `mcp_servers`, so the list lives
as long as the agent or any of its clones. Each SDK-created server is counted once for every such
live list that holds it (a server that a later call reuses is in two lists). When a list is
garbage collected, a `weakref.finalize` callback, which holds the servers but not the list, uses
`loop.call_soon_threadsafe` to release them on the event loop they connected on, because garbage
collection can run in any thread. On that loop, every server whose count drops to zero and that is
still open is closed in a background task, and every service stops tracking it. The callback does
nothing if that loop is already closed. Closed servers are also dropped from the service's tracking
on each call, so a long-lived service doesn't keep growing lists of closed servers.
`cleanup_all_servers()` is still the deterministic way to close them, and closing a server twice
has no effect, so the two paths don't conflict.

This relies on the list the service created. An agent that holds these servers in a list of its own,
for example `agent.clone(mcp_servers=[*agent.mcp_servers, other])`, doesn't keep them open once the
agent the service returned is gone. If such an agent is passed back to `add_tool_servers_to_agent`,
it returns a clone that holds the servers in a list of the service's again.

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
