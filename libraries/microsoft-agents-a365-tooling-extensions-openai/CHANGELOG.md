# Changelog — microsoft-agents-a365-tooling-extensions-openai

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- `McpToolRegistrationService.add_tool_servers_to_agent` reuses an MCP server that an earlier call
  attached only when the server is still connected and its URL and request headers match the
  current turn's. Every other server from an earlier call is replaced or dropped, and closed, also
  when the call fails or is cancelled. Servers the call connected are closed too if it fails or is
  cancelled. Servers you configure on the agent yourself are unchanged. Build the agent for each
  turn, use the returned agent only for that turn, and call `cleanup_all_servers()` when the turn
  ends. `cleanup_all_servers()` closes the servers on every agent the service returned, including
  servers reused from an earlier call.
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
