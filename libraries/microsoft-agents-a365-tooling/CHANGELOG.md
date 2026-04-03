# Changelog

All notable changes to the `microsoft-agents-a365-tooling` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added V1/V2 per-audience token acquisition support in `McpToolServerConfigurationService.list_tool_servers()`. When `authorization`, `auth_handler_name`, and `turn_context` are provided, each MCP server receives its own OAuth token scoped to its audience — V1 servers (no audience, or shared ATG AppId) share a single ATG-scoped token; V2 servers (unique non-ATG audience GUID or `api://` URI) each receive a token scoped to `{audience}/{scope}` (or `{audience}/.default` when scope is absent and pre-consented)
- Added `_attach_per_audience_tokens()` private method to `McpToolServerConfigurationService` — acquires one token per unique scope, caches within the call to avoid redundant exchanges, and attaches `Authorization: Bearer` headers to each server config
- Added `resolve_token_scope_for_server()` utility function to derive the correct OAuth scope for a given `MCPServerConfig` based on its `audience` and `scope` fields
- Added `audience`, `scope`, `publisher`, and `headers` fields to `MCPServerConfig`
- Gateway discovery endpoint bumped to `/agents/v2/{id}/mcpServers`
- `_parse_gateway_server_config()` and `_parse_manifest_server_config()` now map `audience`, `scope`, and `publisher` fields from gateway/manifest responses into `MCPServerConfig`

### Changed

- OpenAI, Semantic Kernel, and Google ADK extensions now pass auth context to `list_tool_servers()` and merge per-server headers (`{**base_headers, **server.headers}`) instead of injecting a single shared ATG token for all servers — fully backward compatible, V1 agents continue to receive the same shared ATG token

### Notes

- **Backward compatible**: agents with V1 manifests (null audience or shared ATG AppId) work identically with the new SDK — no token exchange behaviour changes
- **Migration required for V2**: agents upgraded to V2 blueprint permissions (per-audience MCP servers) require this SDK version. Running a V2 blueprint with the old SDK will result in MCP tool auth failures (401/403)

- Added `send_chat_history` method to `McpToolServerConfigurationService` for sending chat conversation history to the MCP platform for real-time threat protection analysis
- Added `ChatHistoryMessage` Pydantic model for representing individual messages in chat history
- Added `ChatMessageRequest` Pydantic model for the chat history API request payload
- Added `py.typed` marker for PEP 561 compliance, enabling type checker support
