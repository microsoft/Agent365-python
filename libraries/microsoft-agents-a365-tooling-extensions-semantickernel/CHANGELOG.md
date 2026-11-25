# Changelog — microsoft-agents-a365-tooling-extensions-semantickernel

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- `McpToolRegistrationService.add_tool_servers_to_agent` now removes the MCP plugins that an
  earlier call added to the kernel, including copies made by `Kernel.clone()`, before it acquires
  tokens, then adds plugins for the current turn. Plugins you add to the kernel yourself are
  unchanged. Because each call closes the plugins it replaces, turns that run at the same time must
  not share a kernel, or `Kernel.clone()` copies of one; give each turn its own kernel. Use a
  separate service for each turn and call `cleanup_connections()` in a `finally` block when the
  turn ends.
- The MCP connections behind the plugins that `add_tool_servers_to_agent` removes are now closed in
  the background, and they're no longer tracked by the service, so a reused kernel no longer keeps
  one more connection open after every turn. This also closes them for any `Kernel.clone()` copy
  that still shares those plugins. `cleanup_connections()` waits for these closes to finish.
- A server that rejects the connection (for example with HTTP 403) no longer keeps
  `add_tool_servers_to_agent` from returning, and a server whose connection can't be opened is no
  longer added without a connection. Such servers are skipped and the remaining servers are added.
  This watches the plugin's background connection task (`MCPPluginBase._current_task`), and a
  warning is logged if a Semantic Kernel version doesn't set it.
- Cancelling `add_tool_servers_to_agent` while a server is still connecting no longer leaves that
  connection open. The plugin is closed once its connection attempt finishes.
- A server that connects but can't be added to the kernel, for example because its name isn't a
  valid plugin name (such as `mail-tools`), is now closed instead of being left open and untracked.
- MCP plugins that `add_tool_servers_to_agent` adds are now closed once the kernel they were added to
  has been garbage collected, even if `cleanup_connections()` isn't called. A long-lived service
  that gives every turn a new kernel, for example a `Kernel.clone()`, no longer keeps one more
  connection open after each turn. The service also stops tracking plugins once they're closed. A
  `Kernel.clone()` copy of that kernel, or any other kernel that the plugins are copied into,
  doesn't keep them open.

## [2.0.0] - 2026-10-20

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.
