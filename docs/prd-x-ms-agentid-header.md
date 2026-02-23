# PRD: x-ms-agentId Header for MCP Platform Calls

## Overview

Add an `x-ms-agentid` header to all outbound HTTP requests from the tooling package to the MCP platform. This header identifies the calling agent using the best available identifier.

## Problem Statement

The MCP platform needs to identify which agent is making tooling requests for:
- Logging and diagnostics
- Usage analytics

Currently, no consistent agent identifier is sent with MCP platform requests.

## Requirements

### Functional Requirements

1. All HTTP requests to the MCP platform SHALL include the `x-ms-agentid` header
2. The header value SHALL be determined using the following priority:
   1. **Agent Blueprint ID** from TurnContext (highest priority)
   2. **Token Claims** - `xms_par_app_azp` (agent blueprint ID) > `appid` > `azp`
   3. **Application Name** from environment or pyproject.toml (lowest priority fallback)
3. If no identifier is available, the header SHOULD be omitted (not sent with empty value)

### Non-Functional Requirements

1. No additional network calls to retrieve identifiers
2. Minimal performance impact on existing flows
3. Backward compatible - existing integrations continue to work

## Technical Design

### Affected Components

| Package | File | Change |
|---------|------|--------|
| `microsoft-agents-a365-runtime` | `utility.py` | Add `get_agent_id_from_token()` (checks `xms_par_app_azp` → `appid` → `azp`) |
| `microsoft-agents-a365-runtime` | `utility.py` | Add `get_application_name()` helper (reads package name) |
| `microsoft-agents-a365-tooling` | `constants.py` | Add `HEADER_AGENT_ID` and `HEADER_CHANNEL_ID` constants |
| `microsoft-agents-a365-tooling` | `mcp_tool_server_configuration_service.py` | Update `_prepare_gateway_headers()` to include `x-ms-agentid` |

### Identifier Retrieval Strategy

#### 1. Agent Blueprint ID (Highest Priority)

**Source**: `turn_context.activity.from_.agentic_app_blueprint_id`

**Availability**: Only available in agentic request scenarios where a `TurnContext` is present and the request originates from another agent.

**Format**: GUID (e.g., `12345678-1234-1234-1234-123456789abc`)

---

#### 2 & 3. Agent ID from Token (Second/Third Priority)

**Sources** (checked in order):
1. `xms_par_app_azp` claim - Agent Blueprint ID (parent application's Azure app ID)
2. `appid` or `azp` claim - Entra Application ID

**Availability**: Available when an `auth_token` is provided to the tooling methods.

**Implementation**:

```python
# libraries/microsoft-agents-a365-runtime/microsoft_agents_a365/runtime/utility.py
@staticmethod
def get_agent_id_from_token(token: Optional[str]) -> str:
    """
    Decodes the token and retrieves the best available agent identifier.
    Checks claims in priority order: xms_par_app_azp > appid > azp.
    
    Returns empty string for empty/missing tokens (unlike get_app_id_from_token
    which returns a default GUID).
    """
    if not token or not token.strip():
        return ""

    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        # Priority: xms_par_app_azp (agent blueprint ID) > appid > azp
        return decoded.get("xms_par_app_azp") or decoded.get("appid") or decoded.get("azp") or ""
    except (jwt.DecodeError, jwt.InvalidTokenError):
        return ""
```

**Format**: GUID (e.g., `12345678-1234-1234-1234-123456789abc`)

---

#### 4. Application Name (Lowest Priority Fallback)

**Source**: Application's pyproject.toml `name` field or environment variable

**Strategy**:
1. Check `AGENT365_APPLICATION_NAME` environment variable
2. Fall back to reading and caching the application's `pyproject.toml` name field
3. If neither available, omit the header

**Implementation**:

```python
# libraries/microsoft-agents-a365-runtime/microsoft_agents_a365/runtime/utility.py
_cached_application_name: Optional[str] = None

@staticmethod
def get_application_name() -> Optional[str]:
    """Gets the application name from environment or pyproject.toml."""
    # First try environment variable
    env_name = os.environ.get("AGENT365_APPLICATION_NAME")
    if env_name:
        return env_name

    # Fall back to cached pyproject.toml name
    if Utility._cached_application_name is None:
        Utility._cached_application_name = Utility._read_application_name()
    
    return Utility._cached_application_name or None
```

---

### Implementation

#### Updated Header Preparation

```python
# libraries/microsoft-agents-a365-tooling/.../mcp_tool_server_configuration_service.py
def _prepare_gateway_headers(
    self, 
    auth_token: str, 
    turn_context: Optional[TurnContext],
    options: ToolOptions
) -> Dict[str, str]:
    """Prepares headers for tooling gateway requests."""
    headers = {
        Constants.Headers.AUTHORIZATION: f"{Constants.Headers.BEARER_PREFIX} {auth_token}",
        Constants.Headers.USER_AGENT: RuntimeUtility.get_user_agent_header(
            options.orchestrator_name
        ),
    }
    
    # Add x-ms-agentid header with priority fallback
    agent_id = self._resolve_agent_id_for_header(auth_token, turn_context)
    if agent_id:
        headers[Constants.Headers.AGENT_ID] = agent_id
    
    return headers

def _resolve_agent_id_for_header(
    self,
    auth_token: str,
    turn_context: Optional[TurnContext]
) -> Optional[str]:
    """Resolves the best available agent identifier for the x-ms-agentid header."""
    # Priority 1: Agent Blueprint ID from TurnContext
    try:
        if turn_context and turn_context.activity and turn_context.activity.from_:
            blueprint_id = getattr(turn_context.activity.from_, 'agentic_app_blueprint_id', None)
            if blueprint_id:
                return blueprint_id
    except (AttributeError, TypeError):
        pass
    
    # Priority 2 & 3: Agent ID from token (xms_par_app_azp > appid > azp)
    agent_id = RuntimeUtility.get_agent_id_from_token(auth_token)
    if agent_id:
        return agent_id
    
    # Priority 4: Application name
    return RuntimeUtility.get_application_name()
```

### Call Sites Summary

| Call Site | auth_token | turn_context | Gets `x-ms-agentid`? |
|-----------|-----------|-------------|----------------------|
| `_load_servers_from_gateway()` | ✅ | ❌ (None currently) | ✅ Yes (from token/app name) |
| `send_chat_history()` | ❌ | ✅ | ❌ No (authToken required) |

**Note**: The `x-ms-agentid` header is only added when `auth_token` is present. `send_chat_history()` does not pass an auth token, so it won't include this header.

---

## Open Questions

### Q1: Application Name Strategy ✅ RESOLVED

**Decision**: Use `AGENT365_APPLICATION_NAME` environment variable as primary, with pyproject.toml fallback. Cache the pyproject.toml read to avoid repeated file I/O.

### Q2: Header Name Casing ✅ RESOLVED

**Decision**: Use `x-ms-agentid` (all lowercase, case insensitive).

HTTP headers are case-insensitive per RFC 7230, so the server will accept any casing. Using lowercase is the conventional choice.

### Q3: TurnContext Availability ✅ RESOLVED

**Decision**: For this initial implementation, we will pass `None` for turn_context in `_load_servers_from_gateway()` since the current `list_tool_servers` signature doesn't accept it. The agent ID will be resolved from the token or application name.

A future enhancement can add a new overloaded signature similar to the Node.js SDK that accepts `TurnContext`.

---

## Testing Strategy

### Unit Tests

1. Test `get_agent_id_from_token()` with each priority level:
   - Token with `xms_par_app_azp` → returns blueprint ID from token
   - No `xms_par_app_azp`, token with `appid` → returns Entra app ID
   - No `appid`, token with `azp` → returns azp claim
   - No token claims → returns empty string
   - Empty/invalid token → returns empty string
2. Test `get_application_name()`:
   - Returns env var when set
   - Returns pyproject.toml name when env not set
   - Returns None when nothing available
   - Caches the result
3. Test `_resolve_agent_id_for_header()`:
   - TurnContext with `agentic_app_blueprint_id` → returns blueprint ID
   - No blueprint ID, token with claims → returns token claim
   - No claims → returns application name
   - Nothing available → returns None
4. Test `_prepare_gateway_headers()`:
   - Includes `x-ms-agentid` when identifier available
   - Omits header when no identifier available

### Integration Tests

1. Verify header is sent in `list_tool_servers()` requests
2. Verify header is NOT sent in `send_chat_history()` requests (no authToken)

---

## Breaking Changes

**None** - This implementation is fully backward compatible.

---

## Rollout Plan

1. **Phase 1**: Add utility methods and `x-ms-agentid` header (this PR)
2. **Phase 2**: Add overloaded `list_tool_servers()` signature with TurnContext (future)
3. **Phase 3**: Update documentation and samples

---

## Dependencies

- Runtime package for token utility (already exists)
- PyJWT library (already a dependency)
- No new external dependencies required

---

## Success Metrics

1. 100% of MCP platform requests include `x-ms-agentid` header (when identifier available)
2. No increase in request latency
3. No breaking changes for existing consumers
