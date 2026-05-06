# Changelog

All notable changes to the `microsoft-agents-a365-tooling` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added MCP V1/V2 per-audience token acquisition support in `McpToolServerConfigurationService.list_tool_servers()`. When `authorization`, `auth_handler_name`, and `turn_context` are provided, each MCP server receives its own OAuth token scoped to its audience — V1 servers (no audience, or shared ATG AppId) share a single ATG-scoped token; V2 servers (unique non-ATG audience GUID or `api://` URI) each receive a token scoped to `{audience}/{scope}` (or `{audience}/.default` when scope is absent and pre-consented)
- Added `_attach_per_audience_tokens()` private method to `McpToolServerConfigurationService` — acquires one token per unique scope, caches within the call to avoid redundant exchanges, and attaches `Authorization: Bearer` headers to each server config
- Added `_create_dev_token_acquirer()` private method to `McpToolServerConfigurationService` — returns a `TokenAcquirer` closure that reads pre-acquired tokens from environment variables written by the `a365 develop get-token` CLI. Resolution order per server: (1) `BEARER_TOKEN_<MCP_SERVER_NAME_UPPER>` (keyed on `mcp_server_name`, uppercased), then (2) `BEARER_TOKEN` shared fallback. Any existing `Bearer ` prefix (any casing) is stripped before the token is returned so the `Authorization` header is never doubled
- Added `_create_obo_token_acquirer()` private method to `McpToolServerConfigurationService` — returns a `TokenAcquirer` closure that performs an OBO token exchange via `Authorization.exchange_token()` for production use; one exchange per unique audience scope
- Added `resolve_token_scope_for_server()` utility function to derive the correct OAuth scope for a given `MCPServerConfig` based on its `audience` and `scope` fields
- Added `audience`, `scope`, `publisher`, and `headers` fields to `MCPServerConfig`
- Gateway discovery endpoint bumped to `/agents/v2/{id}/mcpServers`
- `_parse_gateway_server_config()` and `_parse_manifest_server_config()` merged into a single `_parse_server_config()` method — both gateway and manifest payloads share the same JSON field schema; the unified method maps `audience`, `scope`, and `publisher` fields from either source into `MCPServerConfig`

### Changed

- OpenAI, Semantic Kernel, and Google ADK extensions now pass auth context to `list_tool_servers()` and merge per-server headers (`{**base_headers, **server.headers}`) instead of injecting a single shared ATG token for all servers — fully backward compatible, V1 agents continue to receive the same shared ATG token
- `_extract_server_unique_name()` now falls back to `mcpServerName` when `mcpServerUniqueName` is absent from the manifest or gateway response
- `_parse_server_config()` (the unified replacement for the former `_parse_manifest_server_config()` / `_parse_gateway_server_config()`) now normalizes `"null"` scope strings and `"default"` audience strings to `None` to prevent incorrect V2 token scope resolution
- `resolve_token_scope_for_server()` now treats `"default"` audience as V1 (shared ATG token) as a defense-in-depth guard

### Notes

- **Backward compatible**: agents with V1 manifests (null audience or shared ATG AppId) work identically with the new SDK — no token exchange behaviour changes
- **Migration required for V2**: agents upgraded to V2 blueprint permissions (per-audience MCP servers) require this SDK version. Running a V2 blueprint with the old SDK will result in MCP tool auth failures (401/403)
- **Local dev token flow**: run `a365 develop get-token` before starting the agent locally; the CLI writes `BEARER_TOKEN` (shared fallback) and `BEARER_TOKEN_<MCP_SERVER_NAME_UPPER>` (per-server, keyed on the server's `mcpServerName` value uppercased) to the environment, which the SDK reads automatically during manifest-based discovery

- Added `send_chat_history` method to `McpToolServerConfigurationService` for sending chat conversation history to the MCP platform for real-time threat protection analysis
- Added `ChatHistoryMessage` Pydantic model for representing individual messages in chat history
- Added `ChatMessageRequest` Pydantic model for the chat history API request payload
- Added `py.typed` marker for PEP 561 compliance, enabling type checker support
