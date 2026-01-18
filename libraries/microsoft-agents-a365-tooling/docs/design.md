# Tooling - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling` package.

## Overview

The tooling package provides MCP (Model Context Protocol) tool server configuration and discovery services. It enables agents to dynamically discover and connect to tool servers for extending agent capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Public API                                │
│  McpToolServerConfigurationService | MCPServerConfig            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              McpToolServerConfigurationService                   │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │   Development Mode   │    │   Production Mode   │            │
│  │                     │    │                     │            │
│  │ ToolingManifest.json│    │  Tooling Gateway    │            │
│  │    (local file)     │    │   (HTTP endpoint)   │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCPServerConfig[]                            │
│  { mcp_server_name, mcp_server_unique_name (URL) }              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### McpToolServerConfigurationService ([services/mcp_tool_server_configuration_service.py](../microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py))

The main service for discovering and configuring MCP tool servers.

```python
from microsoft_agents_a365.tooling import McpToolServerConfigurationService, MCPServerConfig

service = McpToolServerConfigurationService()

# Discover tool servers
servers = await service.list_tool_servers(
    agentic_app_id="app-id-123",
    auth_token="Bearer token",
    options=ToolOptions(orchestrator_name="LangChain")
)

for server in servers:
    print(f"Name: {server.mcp_server_name}")
    print(f"URL: {server.mcp_server_unique_name}")
```

#### Environment Detection

The service automatically selects the configuration source based on the `ENVIRONMENT` variable:

| Environment | Source | Description |
|-------------|--------|-------------|
| `Development` | `ToolingManifest.json` | Local file-based configuration |
| Other (default) | Tooling Gateway | HTTP endpoint discovery |

```python
# Set environment for development mode
os.environ["ENVIRONMENT"] = "Development"
```

#### Development Mode: Manifest-Based Configuration

In development mode, the service reads from `ToolingManifest.json`:

```json
{
  "mcpServers": [
    {
      "mcpServerName": "mailMCPServer",
      "mcpServerUniqueName": "mcp_MailTools"
    },
    {
      "mcpServerName": "sharePointMCPServer",
      "mcpServerUniqueName": "mcp_SharePointTools"
    }
  ]
}
```

**Search locations for manifest file:**
1. Current working directory
2. Parent directory
3. Project root (relative to package location)

The `mcpServerUniqueName` is transformed into a full URL using `build_mcp_server_url()`.

#### Production Mode: Gateway-Based Configuration

In production mode, the service calls the tooling gateway endpoint:

```
GET https://{gateway}/mcp/servers?agentId={agentic_app_id}
Authorization: Bearer {auth_token}
User-Agent: Agent365SDK/0.1.0 (...)
```

The gateway returns the same JSON structure, but `mcpServerUniqueName` contains the full endpoint URL.

### MCPServerConfig ([models/mcp_server_config.py](../microsoft_agents_a365/tooling/models/mcp_server_config.py))

Data class representing an MCP server configuration:

```python
@dataclass
class MCPServerConfig:
    mcp_server_name: str       # Display name of the tool server
    mcp_server_unique_name: str  # Full URL endpoint for the MCP server
```

### Chat History Service

The service also provides functionality for sending chat history to threat protection platforms:

```python
from microsoft_agents_a365.tooling import McpToolServerConfigurationService
from microsoft_agents_a365.tooling.models import ChatHistoryMessage

service = McpToolServerConfigurationService()

# Send chat history for threat protection
result = await service.send_chat_history(
    turn_context=turn_context,
    chat_history_messages=[
        ChatHistoryMessage(role="user", content="Hello"),
        ChatHistoryMessage(role="assistant", content="Hi there!")
    ],
    options=ToolOptions(orchestrator_name="MyAgent")
)

if result.succeeded:
    print("Chat history sent successfully")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
```

**Required TurnContext properties:**
- `activity.conversation.id` - Conversation identifier
- `activity.id` - Message identifier
- `activity.text` - User message text

### Utility Functions ([utils/utility.py](../microsoft_agents_a365/tooling/utils/utility.py))

Helper functions for URL construction and endpoint discovery:

```python
from microsoft_agents_a365.tooling import (
    get_tooling_gateway_for_digital_worker,
    get_mcp_base_url,
    build_mcp_server_url,
)

# Get tooling gateway endpoint
gateway_url = get_tooling_gateway_for_digital_worker("app-id-123")

# Get MCP base URL from environment
base_url = get_mcp_base_url()

# Build full MCP server URL
full_url = build_mcp_server_url("mcp_MailTools")
```

### Constants ([utils/constants.py](../microsoft_agents_a365/tooling/utils/constants.py))

HTTP header constants:

```python
class Constants:
    class Headers:
        AUTHORIZATION = "Authorization"
        BEARER_PREFIX = "Bearer"
        USER_AGENT = "User-Agent"
```

## Data Models

### ToolOptions

```python
@dataclass
class ToolOptions:
    orchestrator_name: str | None = None  # Name for User-Agent header
```

### ChatHistoryMessage

```python
@dataclass
class ChatHistoryMessage:
    role: str      # "user", "assistant", or "system"
    content: str   # Message content
```

### ChatMessageRequest

```python
@dataclass
class ChatMessageRequest:
    conversation_id: str
    message_id: str
    user_message: str
    chat_history: List[ChatHistoryMessage]

    def to_dict(self) -> dict:
        # Serialization for HTTP request
```

## Design Patterns

### Strategy Pattern

The service uses the Strategy pattern to select between manifest-based and gateway-based configuration loading:

```python
def list_tool_servers(self, ...):
    if self._is_development_scenario():
        return self._load_servers_from_manifest()  # Strategy A
    else:
        return await self._load_servers_from_gateway(...)  # Strategy B
```

### Async/Await Pattern

Gateway communication uses async/await for non-blocking HTTP calls:

```python
async with aiohttp.ClientSession() as session:
    async with session.get(endpoint, headers=headers) as response:
        if response.status == 200:
            return await self._parse_gateway_response(response)
```

### Result Pattern

The `send_chat_history` method uses `OperationResult` from the runtime package:

```python
async def send_chat_history(self, ...) -> OperationResult:
    try:
        # Send request
        return OperationResult.success()
    except Exception as ex:
        return OperationResult.failed(OperationError(ex))
```

## File Structure

```
microsoft_agents_a365/tooling/
├── __init__.py                           # Public API exports
├── models/
│   ├── __init__.py
│   ├── mcp_server_config.py              # MCPServerConfig dataclass
│   ├── tool_options.py                   # ToolOptions dataclass
│   ├── chat_history_message.py           # ChatHistoryMessage dataclass
│   └── chat_message_request.py           # ChatMessageRequest dataclass
├── services/
│   ├── __init__.py
│   └── mcp_tool_server_configuration_service.py  # Main service
└── utils/
    ├── __init__.py
    ├── constants.py                       # HTTP header constants
    └── utility.py                         # URL construction utilities
```

## Environment Variables

| Variable | Purpose | Values |
|----------|---------|--------|
| `ENVIRONMENT` | Controls dev vs prod mode | `Development`, `Production` (default) |
| `MCP_BASE_URL` | Base URL for MCP servers (dev mode) | URL string |

## Error Handling

The service provides detailed error messages for common failures:

```python
# Validation errors
ValueError("agentic_app_id cannot be empty or None")
ValueError("auth_token cannot be empty or None")

# HTTP errors
Exception(f"HTTP {status}: {response_text}")

# JSON parsing errors
Exception(f"Failed to parse MCP server configuration response: {error}")

# Connection errors
Exception(f"Failed to connect to MCP configuration endpoint: {error}")
```

## Testing

Tests are located in `tests/tooling/`:

```bash
# Run all tooling tests
pytest tests/tooling/ -v

# Run specific test
pytest tests/tooling/test_mcp_tool_server_configuration_service.py -v
```

## Dependencies

- `aiohttp` - Async HTTP client for gateway communication
- `microsoft-agents-hosting-core` - TurnContext type
- `microsoft-agents-a365-runtime` - OperationResult, Utility

## Integration with Framework Extensions

The tooling package is extended by framework-specific packages:

| Extension Package | Purpose |
|-------------------|---------|
| `tooling-extensions-agentframework` | Microsoft Agents SDK integration |
| `tooling-extensions-azureaifoundry` | Azure AI Foundry integration |
| `tooling-extensions-openai` | OpenAI function calling integration |
| `tooling-extensions-semantickernel` | Semantic Kernel plugin integration |

These extensions adapt the `MCPServerConfig` objects to framework-specific tool definitions.
