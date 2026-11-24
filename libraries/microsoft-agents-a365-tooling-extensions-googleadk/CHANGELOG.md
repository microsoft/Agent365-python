# Changelog — microsoft-agents-a365-tooling-extensions-googleadk

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- `McpToolRegistrationService.add_tool_servers_to_agent` now removes the MCP toolsets that an
  earlier call added to the agent before it acquires tokens, then adds toolsets for the current
  turn. Previously, toolsets from earlier calls stayed on an agent that was reused across turns.
  Tools you configure on the agent yourself are unchanged. Turns that run concurrently must each
  use their own agent.

## [2.0.0] - 2026-10-20

### Security

- Requires `google-adk >= 1.28.1, < 2.0.0` to address CVE-2026-4810.
- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`,
  `python-multipart >= 0.0.30`, and `pyasn1 >= 0.6.4`.
