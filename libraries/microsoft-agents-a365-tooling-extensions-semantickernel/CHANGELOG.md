# Changelog — microsoft-agents-a365-tooling-extensions-semantickernel

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- `McpToolRegistrationService.add_tool_servers_to_agent` now removes the MCP plugins that an
  earlier call added to the kernel, including copies made by `Kernel.clone()`, before it acquires
  tokens, then adds plugins for the current turn. Plugins you add to the kernel yourself are
  unchanged. Turns that run concurrently must each use their own kernel.
- A server that rejects the connection (for example with HTTP 403) no longer keeps
  `add_tool_servers_to_agent` from returning. The server is skipped and the remaining servers are
  added.
- Cancelling `add_tool_servers_to_agent` while a server is still connecting no longer leaves that
  connection open. The plugin is closed once its connection attempt finishes.

## [2.0.0] - 2026-10-20

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.
