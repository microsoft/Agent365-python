# Changelog

All notable changes to the `microsoft-agents-a365-tooling` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added Microsoft Defender for AI real-time protection (Defender RTP) in `microsoft_agents_a365.tooling.protection.defender`, with no agent-hooks dependency. `DefenderRtpClient.evaluate_hook_context()` sends a fitted copy of an agent-hooks/0.1 context emitted at `input`, `pre_tool_call`, `post_tool_call` or `output` to Defender's prevention endpoint as the agent identity and returns a `DefenderRtpEvaluationResult`; other points return `None` without a call. The copy meets Defender's request validation (UTC timestamp, `target` equal to the point's field, spec-only `tool_call`/`tool_result` members, `tenant.id` set to the agent's tenant, agent/actor/request/model filled from `DefenderRtpAgentContext` when the host did not set them, invalid optional fields repaired or dropped). The envelope (ids, names, roles, session, tenant, actor, model, trace) is built from its spec fields alone and never cut; each content string is cut to at most `max_content_characters` characters and all content shares a budget of four times that: the content under decision, which is sent twice, may use half, and the called tool's declaration, the call's arguments at `post_tool_call`, the other tool declarations, the newest messages, extensions and other members share the rest, in that order. Every string is sent as valid Unicode (lone surrogates become U+FFFD), NaN and infinities as text, and a member of an unexpected shape is ignored. The endpoint must be HTTPS. Every call sends a unique `x-ms-correlation-id`, returned on the result. Token acquisition and the call share one deadline; a timeout, transport or token failure, non-2xx response, or response without a verdict is not evaluated and follows the fail mode (open by default). When the content under decision does not fit, Defender evaluates a truncated copy (`truncated=True`): its deny still blocks, but its allow follows the fail mode. At a tool point the called tool's declaration is searched for among the first 10,000 entries of `tools` and sent first; an allow also follows the fail mode when its description or schema had to be cut, or when `tools` is longer and the called tool is not among those entries
- Added `DefenderRtpOptions.from_environment()` reading `ENABLE_A365_DEFENDER_RTP`, `A365_DEFENDER_RTP_ENDPOINT`, `A365_DEFENDER_RTP_FAIL_MODE`, `A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS` (default 10000), `A365_DEFENDER_RTP_AUTHENTICATION_SCOPE` and `A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS` (default 20000); the fail mode is `open` (default) or `closed` and any other value is rejected, the numeric values are positive integers up to 2147483647, and `validate()` rejects a timeout that is not finite
- Added `DefenderRtpTokenResolvers.from_agentic_connection()`: exchanges the agent identity's assertion from the agent's connection (`get_agentic_application_token`) for its app-only Defender API token over an HTTPS authority. `DefenderRtpClient` caches the token per agent, tenant and scope until it expires, refreshes it in the background within five minutes of expiry (keeping the cached token if the refresh fails), and shares one acquisition between concurrent calls; `prefetch_access_token()` acquires it ahead of the first evaluation. A synchronous token resolver runs on a worker thread, so it never blocks the event loop
- Declared `aiohttp`, which the package already imports, as a dependency
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
