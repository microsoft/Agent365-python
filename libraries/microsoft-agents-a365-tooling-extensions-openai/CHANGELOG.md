# Changelog — microsoft-agents-a365-tooling-extensions-openai

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- `McpToolRegistrationService.add_tool_servers_to_agent` reuses an MCP server that an earlier call
  attached only when the server is still connected and its URL and request headers match the
  current turn's. Every other server from an earlier call is replaced or dropped, and closed, also
  when the call fails or is cancelled. Servers the call connected are closed too if it fails or is
  cancelled. Servers you configure on the agent yourself are unchanged. Because each call closes the
  servers it replaces, turns that run at the same time must not share an agent that the method
  returned, or clones of it. Build the agent for each turn and use the returned agent only for that
  turn. Use a separate service for each turn and call `cleanup_all_servers()` in a `finally` block
  when the turn ends. `cleanup_all_servers()` closes the servers on every agent the service
  returned, including servers reused from an earlier call.
- When `add_tool_servers_to_agent` fails or is cancelled, the servers it closes are also removed
  from the agent you passed in (it gets a new `mcp_servers` list, so clones that share the old list
  are unchanged), so that agent can still run without them.
- MCP servers that `add_tool_servers_to_agent` connects are now closed once the agent it returned
  and every `clone()` of that agent have been garbage collected, even if `cleanup_all_servers()`
  isn't called. A long-lived service that builds a new agent for every turn no longer keeps one
  more connection open after each turn. A server that a later call reuses stays open while any
  agent that holds it is alive. The service also stops tracking servers once they're closed. This
  relies on the `mcp_servers` list the method gives the returned agent, so don't copy these servers
  into a list of your own, for example with `agent.clone(mcp_servers=[...])`.
- MCP servers created by `add_tool_servers_to_agent` now connect and disconnect in a task of their
  own. Closing a server from another task no longer cancels the task that is using it, and a server
  that rejects the connection (for example with HTTP 403) is skipped instead of cancelling the
  turn, so the remaining servers are still added.
- `add_tool_servers_to_agent` now returns `agent.clone(...)`, so guardrails, handoffs, hooks, output
  type, and other agent settings are no longer dropped when MCP servers are added.

## [2.0.0] - 2026-10-20

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.
