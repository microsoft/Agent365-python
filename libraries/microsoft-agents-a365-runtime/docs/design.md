# Runtime - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-runtime` package.

## Overview

The runtime package provides core utilities shared across the Agent365 SDK. It includes:

- Power Platform API endpoint discovery
- JWT token utilities
- Operation result pattern for error handling
- Environment utilities

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Public API                                │
│  PowerPlatformApiDiscovery | Utility | OperationResult          │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Endpoint         │ │ Token            │ │ Result           │
│ Discovery        │ │ Processing       │ │ Pattern          │
│                  │ │                  │ │                  │
│ - Cluster URLs   │ │ - JWT decode     │ │ - Success/Fail   │
│ - Tenant routing │ │ - Agent identity │ │ - Error list     │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## Key Components

### PowerPlatformApiDiscovery ([power_platform_api_discovery.py](../microsoft_agents_a365/runtime/power_platform_api_discovery.py))

Discovers Power Platform API endpoints based on cluster category and tenant ID.

```python
from microsoft_agents_a365.runtime import PowerPlatformApiDiscovery, ClusterCategory

discovery = PowerPlatformApiDiscovery("prod")

# Get tenant-specific endpoint
endpoint = discovery.get_tenant_endpoint("tenant-id-123")
# Returns: "tenantid12.3.tenant.api.powerplatform.com"

# Get island cluster endpoint (for observability)
island_endpoint = discovery.get_tenant_island_cluster_endpoint("tenant-id-123")
# Returns: "il-tenantid12.3.tenant.api.powerplatform.com"

# Get token audience
audience = discovery.get_token_audience()
# Returns: "https://api.powerplatform.com"
```

**Supported Cluster Categories:**

| Category | API Host |
|----------|----------|
| `prod` | `api.powerplatform.com` |
| `firstrelease` | `api.powerplatform.com` |
| `gov` | `api.gov.powerplatform.microsoft.us` |
| `high` | `api.high.powerplatform.microsoft.us` |
| `dod` | `api.appsplatform.us` |
| `mooncake` | `api.powerplatform.partner.microsoftonline.cn` |
| `ex` | `api.powerplatform.eaglex.ic.gov` |
| `rx` | `api.powerplatform.microsoft.scloud` |
| `local` | `api.powerplatform.localhost` |

**Endpoint Generation:**

The endpoint is generated using the tenant ID:
1. Normalize tenant ID (lowercase, remove dashes)
2. Split into prefix and suffix parts
3. Generate: `{prefix}.{suffix}.tenant.{host}`

For island cluster endpoints, prepend `il-` to the result.

### Utility ([utility.py](../microsoft_agents_a365/runtime/utility.py))

Static utility methods for common runtime operations.

#### Token Decoding

```python
from microsoft_agents_a365.runtime import Utility

# Extract App ID from JWT token
app_id = Utility.get_app_id_from_token(jwt_token)
# Looks for 'appid' or 'azp' claims
# Returns empty GUID if token is invalid
```

#### Agent Identity Resolution

```python
# Resolve agent identity from context or token
agent_id = Utility.resolve_agent_identity(turn_context, auth_token)
# Returns agentic instance ID for agentic requests
# Falls back to App ID from token otherwise
```

#### User-Agent Header

```python
# Generate User-Agent header for SDK requests
user_agent = Utility.get_user_agent_header(orchestrator="LangChain")
# Returns: "Agent365SDK/0.1.0 (Windows; Python 3.11; LangChain)"
```

### OperationResult ([operation_result.py](../microsoft_agents_a365/runtime/operation_result.py))

A result pattern for representing success or failure without exceptions.

```python
from microsoft_agents_a365.runtime import OperationResult, OperationError

# Success case - uses singleton instance
result = OperationResult.success()
assert result.succeeded == True
assert result.errors == []

# Failure case - creates new instance
error = OperationError(Exception("Something went wrong"))
result = OperationResult.failed(error)
assert result.succeeded == False
assert len(result.errors) == 1

# Multiple errors
result = OperationResult.failed(
    OperationError(ValueError("Invalid input")),
    OperationError(ConnectionError("Network error"))
)

# Check result
if result.succeeded:
    process_success()
else:
    for error in result.errors:
        log_error(error.message)
```

**Design Notes:**
- `success()` returns a singleton instance for efficiency
- `errors` property returns a defensive copy to protect the singleton
- `failed()` always creates a new instance

### OperationError ([operation_error.py](../microsoft_agents_a365/runtime/operation_error.py))

Wraps exceptions with additional context.

```python
from microsoft_agents_a365.runtime import OperationError

error = OperationError(ValueError("Invalid input"))
print(error.message)  # "Invalid input"
print(error.exception)  # ValueError instance
```

### Environment Utilities ([environment_utils.py](../microsoft_agents_a365/runtime/environment_utils.py))

Environment-specific configuration utilities.

```python
from microsoft_agents_a365.runtime import get_observability_authentication_scope

# Get authentication scope for observability
scope = get_observability_authentication_scope()
```

## Type Definitions

### ClusterCategory

```python
from typing import Literal

ClusterCategory = Literal[
    "local",
    "dev",
    "test",
    "preprod",
    "firstrelease",
    "prod",
    "gov",
    "high",
    "dod",
    "mooncake",
    "ex",
    "rx",
]
```

## Design Patterns

### Result Pattern

The `OperationResult` class implements the Result pattern (also known as Either monad) to handle success/failure without exceptions:

```python
# Instead of:
try:
    result = risky_operation()
    process(result)
except Exception as e:
    handle_error(e)

# Use:
result = risky_operation()  # Returns OperationResult
if result.succeeded:
    process_success()
else:
    handle_errors(result.errors)
```

**Benefits:**
- Explicit error handling in return type
- No hidden control flow from exceptions
- Easy to compose multiple operations
- Thread-safe with singleton success instance

### Singleton Pattern (for OperationResult.success)

```python
class OperationResult:
    _success_instance = None

    @staticmethod
    def success():
        if OperationResult._success_instance is None:
            OperationResult._success_instance = OperationResult(succeeded=True)
        return OperationResult._success_instance
```

**Note:** The `errors` property returns a defensive copy to prevent accidental mutation of the singleton instance.

## File Structure

```
microsoft_agents_a365/runtime/
├── __init__.py                       # Public API exports
├── power_platform_api_discovery.py   # Endpoint discovery
├── utility.py                        # Token and identity utilities
├── operation_result.py               # Result pattern
├── operation_error.py                # Error wrapper
├── environment_utils.py              # Environment configuration
└── version_utils.py                  # Version utilities
```

## Testing

Tests are located in `tests/runtime/`:

```bash
# Run all runtime tests
pytest tests/runtime/ -v

# Run specific test file
pytest tests/runtime/test_power_platform_api_discovery.py -v
pytest tests/runtime/test_utility.py -v
pytest tests/runtime/test_operation_result.py -v
```

## Dependencies

- `pyjwt` - JWT token decoding
- Standard library only for other components

## Usage by Other Packages

The runtime package is used by:

- **observability-core**: `PowerPlatformApiDiscovery` for exporter endpoint resolution
- **tooling**: `Utility` for agent identity resolution and User-Agent generation
- **tooling**: `OperationResult` for `send_chat_history` return type
