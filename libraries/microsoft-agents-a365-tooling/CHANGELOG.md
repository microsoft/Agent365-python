# Changelog

All notable changes to the `microsoft-agents-a365-tooling` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added MCP V1/V2 per-audience token acquisition support in `McpToolServerConfigurationService.list_tool_servers()`. When `authorization`, `auth_handler_name`, and `turn_context` are provided, each MCP server receives its own OAuth token scoped to its audience — V1 servers (no audience, or shared ATG AppId) share a single ATG-scoped token; V2 servers (unique non-ATG audience GUID or `api://` URI) each receive a token scoped to `{audience}/{scope}` (or `{audience}/.default` when scope is absent and pre-consented)
- Added `_attach_per_audience_tokens()` private method to `McpToolServerConfigurationService` — acquires one token per unique scope, caches within the call to avoid redundant exchanges, and attaches `Authorization: Bearer` headers to each server config
- Added `resolve_token_scope_for_server()` utility function to derive the correct OAuth scope for a given `MCPServerConfig` based on its `audience` and `scope` fields
- Added `audience`, `scope`, `publisher`, and `headers` fields to `MCPServerConfig`
- Gateway discovery endpoint bumped to `/agents/v2/{id}/mcpServers`
- `_parse_gateway_server_config()` and `_parse_manifest_server_config()` now map `audience`, `scope`, and `publisher` fields from gateway/manifest responses into `MCPServerConfig`

- Added `_attach_dev_tokens()` private method to `McpToolServerConfigurationService` — reads `BEARER_TOKEN_<SERVER_UNIQUE_NAME>` and `BEARER_TOKEN` environment variables written by the `a365 develop get-token` CLI and attaches per-server `Authorization: Bearer` headers during local dev manifest loading; no-op in production

### Changed

- OpenAI, Semantic Kernel, and Google ADK extensions now pass auth context to `list_tool_servers()` and merge per-server headers (`{**base_headers, **server.headers}`) instead of injecting a single shared ATG token for all servers — fully backward compatible, V1 agents continue to receive the same shared ATG token
- `_extract_server_unique_name()` now falls back to `mcpServerName` when `mcpServerUniqueName` is absent from the manifest or gateway response
- `_parse_manifest_server_config()` and `_parse_gateway_server_config()` now normalize `"null"` scope strings and `"default"` audience strings to `None` to prevent incorrect V2 token scope resolution
- `resolve_token_scope_for_server()` now treats `"default"` audience as V1 (shared ATG token) as a defense-in-depth guard

### Notes

- **Backward compatible**: agents with V1 manifests (null audience or shared ATG AppId) work identically with the new SDK — no token exchange behaviour changes
- **Migration required for V2**: agents upgraded to V2 blueprint permissions (per-audience MCP servers) require this SDK version. Running a V2 blueprint with the old SDK will result in MCP tool auth failures (401/403)
- **Local dev token flow**: run `a365 develop get-token` before starting the agent locally; the CLI writes `BEARER_TOKEN` (V1 shared) and `BEARER_TOKEN_<SERVER_NAME>` (V2 per-server) to the environment, which the SDK reads automatically from the manifest path

- Added `send_chat_history` method to `McpToolServerConfigurationService` for sending chat conversation history to the MCP platform for real-time threat protection analysis
- Added `ChatHistoryMessage` Pydantic model for representing individual messages in chat history
- Added `ChatMessageRequest` Pydantic model for the chat history API request payload
- Added `py.typed` marker for PEP 561 compliance, enabling type checker support
