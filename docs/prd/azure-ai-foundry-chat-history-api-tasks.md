# Azure AI Foundry Chat History API - Implementation Tasks

## Document Information

| Field | Value |
|-------|-------|
| **PRD Reference** | [azure-ai-foundry-chat-history-api.md](azure-ai-foundry-chat-history-api.md) |
| **Target Package** | `microsoft-agents-a365-tooling-extensions-azureaifoundry` |
| **Created** | 2026-01-26 |
| **Status** | Ready for Implementation |

---

## Executive Summary

This task breakdown covers the implementation of a chat history API for the Azure AI Foundry orchestrator in the Microsoft Agent 365 Python SDK. The feature enables developers to send conversation history from Azure AI Foundry Persistent Agents to the MCP platform for real-time threat protection and compliance monitoring.

The implementation follows established patterns from the OpenAI and Agent Framework extensions, adapting them for Azure AI Foundry's unique characteristics: thread-based message access via `AgentsClient` and message retrieval from the Azure AI Agents API rather than in-memory sessions.

The work is organized into three phases: (1) Core implementation of the API methods and helper functions, (2) Comprehensive unit testing following existing test patterns, and (3) Documentation and code quality verification. Each task is scoped for 2-8 hours of work by a junior engineer.

---

## Architecture Impact

### Packages Affected

| Package | Impact Type | Description |
|---------|-------------|-------------|
| `microsoft-agents-a365-tooling-extensions-azureaifoundry` | Modified | Add chat history methods to `McpToolRegistrationService` |
| `tests/tooling/extensions/azureaifoundry/` | New | Create test directory structure and unit tests |

### Key Files

**Modified Files:**
- `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`

**New Files:**
- `tests/tooling/extensions/azureaifoundry/__init__.py`
- `tests/tooling/extensions/azureaifoundry/services/__init__.py`
- `tests/tooling/extensions/azureaifoundry/services/conftest.py`
- `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`

---

## Task Dependency Diagram

```
Phase 1: Core Implementation
    TASK-001 (Imports & Constants)
         |
         v
    TASK-002 (Content Extraction Helper)
         |
         v
    TASK-003 (Message Conversion Helper)
         |
         v
    TASK-004 (send_chat_history_messages API)
         |
         v
    TASK-005 (send_chat_history API)

Phase 2: Testing (can start after TASK-003)
    TASK-006 (Test Directory Setup)
         |
         v
    TASK-007 (Test Fixtures - conftest.py)
         |
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
    TASK-008           TASK-009           TASK-010
    (Validation        (Conversion        (Success Path
     Tests)             Tests)             Tests)
         |                  |                  |
         +------------------+------------------+
         |
         v
    TASK-011 (Error Handling Tests)

Phase 3: Documentation & Quality
    TASK-012 (Docstrings & Examples)
         |
         v
    TASK-013 (Final Quality Checks)
```

---

## Phase 1: Core Implementation

### TASK-001: Add Required Imports and Constants

**Title:** Add imports and orchestrator constant for chat history API

**Description:**
Add the necessary imports from the Azure AI Agents SDK and internal packages to support the chat history API implementation. This establishes the foundation for subsequent implementation tasks.

**Acceptance Criteria:**
- [ ] Import `Sequence`, `List`, `Optional` from typing module
- [ ] Import `uuid` for generating message IDs
- [ ] Import `datetime`, `timezone` from datetime module
- [ ] Import `ThreadMessage`, `MessageTextContent` from `azure.ai.agents.models`
- [ ] Import `AgentsClient` from `azure.ai.agents`
- [ ] Import `OperationError`, `OperationResult` from `microsoft_agents_a365.runtime`
- [ ] Import `ChatHistoryMessage` from `microsoft_agents_a365.tooling.models`
- [ ] Verify existing `_orchestrator_name = "AzureAIFoundry"` class constant is present
- [ ] All imports follow the existing import ordering in the file (stdlib, third-party, local)
- [ ] No linting errors when running `uv run --frozen ruff check .`

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference:** See imports in OpenAI extension (`libraries/microsoft-agents-a365-tooling-extensions-openai/microsoft_agents_a365/tooling/extensions/openai/mcp_tool_registration_service.py` lines 1-35)
- **Pattern:** Follow existing import grouping: stdlib, Azure SDK, microsoft_agents, microsoft_agents_a365

**Estimated Time:** 1-2 hours

---

### TASK-002: Implement Content Extraction Helper Method

**Title:** Implement `_extract_content_from_message()` private helper method

**Description:**
Implement a private helper method that extracts text content from a `ThreadMessage` object. Azure AI Foundry messages store content as a list of `MessageContent` items, and text must be extracted from `MessageTextContent` items and concatenated.

**Acceptance Criteria:**
- [ ] Method signature: `def _extract_content_from_message(self, message: ThreadMessage) -> str`
- [ ] Iterates through `message.content` list
- [ ] For each item that is `MessageTextContent`, extracts `text.value` property
- [ ] Concatenates all text values with space separator
- [ ] Returns empty string if `message.content` is None or empty
- [ ] Returns empty string if no `MessageTextContent` items found
- [ ] Handles `MessageTextContent` items where `text` or `text.value` is None gracefully
- [ ] Method is private (prefixed with underscore)
- [ ] Type hints on parameters and return type
- [ ] Docstring with Args, Returns sections

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference .NET:** See Appendix A.2 in PRD for .NET `ExtractContentFromMessage` implementation
- **Reference Python:** See `_extract_content()` in OpenAI extension (lines 541-599) for pattern
- **Pattern:** Use `isinstance()` check to identify `MessageTextContent` items
- **Key insight:** Azure SDK uses `text.value` not `text` directly for the actual text string

**Code Skeleton:**
```python
def _extract_content_from_message(self, message: ThreadMessage) -> str:
    """
    Extract text content from a ThreadMessage's content items.

    Args:
        message: Azure AI Foundry ThreadMessage object.

    Returns:
        Concatenated text content as string, or empty string if no text found.
    """
    if message.content is None or len(message.content) == 0:
        return ""

    text_parts: List[str] = []

    for content_item in message.content:
        if isinstance(content_item, MessageTextContent):
            # Extract text.value safely
            if content_item.text is not None and content_item.text.value:
                text_parts.append(content_item.text.value)

    return " ".join(text_parts)
```

**Estimated Time:** 2-3 hours

---

### TASK-003: Implement Message Conversion Helper Method

**Title:** Implement `_convert_thread_messages_to_chat_history()` private helper method

**Description:**
Implement a private helper method that converts a sequence of Azure AI Foundry `ThreadMessage` objects to a list of `ChatHistoryMessage` objects. This method handles validation, filtering, and transformation of messages.

**Acceptance Criteria:**
- [ ] Method signature: `def _convert_thread_messages_to_chat_history(self, messages: Sequence[ThreadMessage]) -> List[ChatHistoryMessage]`
- [ ] Filters out messages where `message` is None (logs warning)
- [ ] Filters out messages where `message.id` is None (logs warning with context)
- [ ] Filters out messages where `message.role` is None (logs warning with message ID)
- [ ] Filters out messages where extracted content is empty/whitespace (logs warning with message ID)
- [ ] Converts `message.role` enum to lowercase string ("user", "assistant", "system")
- [ ] Maps `message.id` to `ChatHistoryMessage.id`
- [ ] Maps extracted content to `ChatHistoryMessage.content`
- [ ] Maps `message.created_at` to `ChatHistoryMessage.timestamp`
- [ ] Uses `_extract_content_from_message()` for content extraction
- [ ] Returns empty list if all messages filtered (logs warning)
- [ ] Skips messages without ID (no UUID generated; logs warning)
- [ ] Type hints on parameters and return type
- [ ] Comprehensive docstring

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference:** See `_convert_chat_messages_to_history()` in Agent Framework extension (lines 153-212)
- **Reference:** See `_convert_openai_messages_to_chat_history()` in OpenAI extension (lines 427-451)
- **Pattern:** Iterate, validate, convert, filter; use logging for skipped messages
- **Key insight:** Azure SDK role is an enum - use `.value` to get string, then `.lower()`

**Logging Messages (from PRD Section 5.5):**
- "Skipping null message"
- "Skipping message with null ID"
- "Skipping message with null role (ID: {id})"
- "Skipping message {id} with empty content"
- "All messages were filtered out during conversion"

**Estimated Time:** 3-4 hours

---

### TASK-004: Implement `send_chat_history_messages()` Public Method

**Title:** Implement `send_chat_history_messages()` public API method

**Description:**
Implement the primary public method that accepts a sequence of `ThreadMessage` objects and sends them to the MCP platform. This method handles input validation, message conversion, and delegation to the core service.

**Acceptance Criteria:**
- [ ] Method is `async`
- [ ] Method signature matches PRD Section 4.1.1:
  ```python
  async def send_chat_history_messages(
      self,
      turn_context: TurnContext,
      messages: Sequence[ThreadMessage],
      tool_options: Optional[ToolOptions] = None,
  ) -> OperationResult:
  ```
- [ ] Raises `ValueError` if `turn_context` is None with message "turn_context cannot be None"
- [ ] Raises `ValueError` if `messages` is None with message "messages cannot be None"
- [ ] Creates default `ToolOptions` with `orchestrator_name="AzureAIFoundry"` if not provided
- [ ] Sets orchestrator_name to "AzureAIFoundry" if options provided but orchestrator_name is None
- [ ] Converts messages using `_convert_thread_messages_to_chat_history()`
- [ ] Always delegates to `self._mcp_server_configuration_service.send_chat_history()` even for empty/filtered messages (to register current user message)
- [ ] Catches unexpected exceptions and returns `OperationResult.failed(OperationError(ex))`
- [ ] Re-raises `ValueError` exceptions (validation errors should propagate)
- [ ] Logs entry with message count at INFO level
- [ ] Logs success with message count at INFO level
- [ ] Logs failure with error at ERROR level
- [ ] Comprehensive docstring with example

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference:** See `send_chat_history_messages()` in OpenAI extension (lines 332-421)
- **Reference:** See `send_chat_history_messages()` in Agent Framework extension (lines 214-285)
- **Pattern:** Validate -> Convert -> Delegate -> Handle errors
- **Note:** The service already has `_mcp_server_configuration_service` initialized in `__init__`

**Code Structure:**
```python
async def send_chat_history_messages(
    self,
    turn_context: TurnContext,
    messages: Sequence[ThreadMessage],
    tool_options: Optional[ToolOptions] = None,
) -> OperationResult:
    # 1. Input validation (raise ValueError)
    # 2. Log entry
    # 3. Set default options
    # 4. Convert messages (may result in empty list if all filtered)
    # 5. Try: delegate to core service (always, even if empty)
    # 6. Except ValueError: re-raise
    # 7. Except Exception: log, return failed
```

**Estimated Time:** 3-4 hours

---

### TASK-005: Implement `send_chat_history()` Public Method

**Title:** Implement `send_chat_history()` public API method with client-based retrieval

**Description:**
Implement the convenience method that retrieves messages from Azure AI Foundry using an `AgentsClient` and thread ID, then delegates to `send_chat_history_messages()`. This is the primary method most developers will use.

**Acceptance Criteria:**
- [ ] Method is `async`
- [ ] Method signature matches PRD Section 4.1.2:
  ```python
  async def send_chat_history(
      self,
      agents_client: AgentsClient,
      thread_id: str,
      turn_context: TurnContext,
      tool_options: Optional[ToolOptions] = None,
  ) -> OperationResult:
  ```
- [ ] Raises `ValueError` if `agents_client` is None with message "agents_client cannot be None"
- [ ] Raises `ValueError` if `thread_id` is None or whitespace with message "thread_id cannot be empty"
- [ ] Raises `ValueError` if `turn_context` is None with message "turn_context cannot be None"
- [ ] Retrieves messages using `agents_client.messages.list(thread_id=thread_id)`
- [ ] Converts async iterable to list using `async for` or `list()` comprehension
- [ ] Logs retrieved message count at INFO level
- [ ] Delegates to `send_chat_history_messages()` with retrieved messages
- [ ] Catches Azure SDK errors and returns `OperationResult.failed(OperationError(ex))`
- [ ] Re-raises `ValueError` exceptions
- [ ] Comprehensive docstring with example

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference:** See `send_chat_history_from_store()` in Agent Framework extension (lines 287-331)
- **Reference:** See `send_chat_history()` in OpenAI extension (lines 253-330)
- **Key insight:** Azure SDK returns `AsyncIterable[ThreadMessage]` - must collect to list
- **Pattern:** Validate -> Retrieve -> Delegate

**Code Structure:**
```python
async def send_chat_history(
    self,
    agents_client: AgentsClient,
    thread_id: str,
    turn_context: TurnContext,
    tool_options: Optional[ToolOptions] = None,
) -> OperationResult:
    # 1. Input validation (raise ValueError)
    # 2. Try: retrieve messages from client
    # 3. Log retrieved count
    # 4. Delegate to send_chat_history_messages
    # 5. Except ValueError: re-raise
    # 6. Except Exception: log, return failed
```

**Message Retrieval Pattern:**
```python
messages: List[ThreadMessage] = []
async for message in agents_client.messages.list(thread_id=thread_id):
    messages.append(message)
self._logger.info(f"Retrieved {len(messages)} messages from thread {thread_id}")
```

**Estimated Time:** 2-3 hours

---

## Phase 2: Testing

### TASK-006: Create Test Directory Structure

**Title:** Set up test directory structure for Azure AI Foundry extension

**Description:**
Create the directory structure and `__init__.py` files for the Azure AI Foundry extension tests, following the existing pattern for other extensions.

**Acceptance Criteria:**
- [ ] Create `tests/tooling/extensions/azureaifoundry/__init__.py`
- [ ] Create `tests/tooling/extensions/azureaifoundry/services/__init__.py`
- [ ] All `__init__.py` files include copyright header
- [ ] Directory structure matches pattern from Agent Framework extension
- [ ] Files can be imported without errors

**Technical Guidance:**
- **Reference:** See `tests/tooling/extensions/agentframework/` structure
- **Reference:** See `tests/tooling/extensions/openai/` structure

**File Content Template:**
```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```

**Estimated Time:** 30 minutes

---

### TASK-007: Create Test Fixtures (conftest.py)

**Title:** Implement pytest fixtures for Azure AI Foundry chat history tests

**Description:**
Create a `conftest.py` file with pytest fixtures that provide mock objects for Azure AI Foundry SDK types. These fixtures will be used across all test files.

**Acceptance Criteria:**
- [ ] Create `tests/tooling/extensions/azureaifoundry/services/conftest.py`
- [ ] Copyright header present
- [ ] `mock_turn_context` fixture - creates mock `TurnContext` with valid activity
- [ ] `mock_agents_client` fixture - creates mock `AgentsClient` with async `messages.list()`
- [ ] `mock_thread_message` fixture - creates single mock `ThreadMessage`
- [ ] `sample_thread_messages` fixture - creates list of mock `ThreadMessage` objects
- [ ] `mock_message_text_content` fixture - creates mock `MessageTextContent`
- [ ] `mock_role_user`, `mock_role_assistant`, `mock_role_system` fixtures for role enums
- [ ] `service` fixture - creates `McpToolRegistrationService` with mocked core service
- [ ] All fixtures have docstrings
- [ ] Fixtures use `unittest.mock.Mock` and `AsyncMock` appropriately

**Technical Guidance:**
- **File:** `tests/tooling/extensions/azureaifoundry/services/conftest.py`
- **Reference:** See `tests/tooling/extensions/openai/conftest.py` for patterns
- **Reference:** See `tests/tooling/extensions/agentframework/services/test_send_chat_history.py` for fixture style
- **Key insight:** Azure SDK types need careful mocking of nested attributes

**Mock ThreadMessage Structure:**
```python
@pytest.fixture
def mock_thread_message():
    """Create a mock ThreadMessage."""
    message = Mock()
    message.id = "msg-123"
    message.role = Mock()
    message.role.value = "user"  # Enum-like behavior
    message.created_at = datetime.now(timezone.utc)

    # Content is a list of MessageContent items
    text_content = Mock(spec=MessageTextContent)
    text_content.text = Mock()
    text_content.text.value = "Hello, world!"
    message.content = [text_content]

    return message
```

**Estimated Time:** 2-3 hours

---

### TASK-008: Implement Input Validation Tests

**Title:** Write unit tests for input validation scenarios

**Description:**
Implement comprehensive unit tests for input validation in both `send_chat_history_messages()` and `send_chat_history()` methods.

**Acceptance Criteria:**
- [ ] Create `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`
- [ ] Copyright header present
- [ ] All tests marked with `@pytest.mark.asyncio` and `@pytest.mark.unit`
- [ ] Test class: `TestInputValidation`
- [ ] Test: `test_send_chat_history_messages_validates_turn_context_none`
- [ ] Test: `test_send_chat_history_messages_validates_messages_none`
- [ ] Test: `test_send_chat_history_messages_empty_list_still_calls_core_service`
- [ ] Test: `test_send_chat_history_validates_agents_client_none`
- [ ] Test: `test_send_chat_history_validates_thread_id_none`
- [ ] Test: `test_send_chat_history_validates_thread_id_empty`
- [ ] Test: `test_send_chat_history_validates_thread_id_whitespace`
- [ ] Test: `test_send_chat_history_validates_turn_context_none`
- [ ] Each test verifies correct `ValueError` message
- [ ] Tests use fixtures from conftest.py

**Technical Guidance:**
- **File:** `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`
- **Reference:** See `TestInputValidation` in `tests/tooling/extensions/openai/test_send_chat_history.py`
- **Reference:** See validation tests in Agent Framework tests
- **Pattern:** Use `pytest.raises(ValueError, match="expected message")`

**Estimated Time:** 2-3 hours

---

### TASK-009: Implement Message Conversion Tests

**Title:** Write unit tests for message conversion logic

**Description:**
Implement unit tests for the `_convert_thread_messages_to_chat_history()` and `_extract_content_from_message()` helper methods.

**Acceptance Criteria:**
- [ ] Test class: `TestMessageConversion`
- [ ] Test: `test_extract_content_from_single_text_item`
- [ ] Test: `test_extract_content_from_multiple_text_items`
- [ ] Test: `test_extract_content_handles_empty_content_list`
- [ ] Test: `test_extract_content_handles_none_content`
- [ ] Test: `test_extract_content_handles_none_text_value`
- [ ] Test: `test_convert_messages_extracts_id_correctly`
- [ ] Test: `test_convert_messages_extracts_role_correctly`
- [ ] Test: `test_convert_messages_extracts_timestamp_correctly`
- [ ] Test: `test_convert_messages_filters_null_message`
- [ ] Test: `test_convert_messages_filters_null_id`
- [ ] Test: `test_convert_messages_filters_null_role`
- [ ] Test: `test_convert_messages_filters_empty_content`
- [ ] Test: `test_convert_messages_filters_whitespace_only_content`
- [ ] Test: `test_convert_messages_all_filtered_returns_empty_list`
- [ ] Test: `test_convert_messages_role_enum_to_lowercase`

**Technical Guidance:**
- **File:** `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`
- **Reference:** See `tests/tooling/extensions/openai/test_message_conversion.py`
- **Pattern:** Direct method calls on service instance, verify return values

**Estimated Time:** 3-4 hours

---

### TASK-010: Implement Success Path Tests

**Title:** Write unit tests for successful execution paths

**Description:**
Implement unit tests that verify the happy path scenarios for both API methods, including proper delegation to the core service.

**Acceptance Criteria:**
- [ ] Test class: `TestSuccessPath`
- [ ] Test: `test_send_chat_history_messages_success`
- [ ] Test: `test_send_chat_history_messages_with_tool_options`
- [ ] Test: `test_send_chat_history_messages_default_orchestrator_name`
- [ ] Test: `test_send_chat_history_messages_delegates_to_core_service`
- [ ] Test: `test_send_chat_history_messages_converts_messages_correctly`
- [ ] Test: `test_send_chat_history_success`
- [ ] Test: `test_send_chat_history_retrieves_from_client`
- [ ] Test: `test_send_chat_history_delegates_to_send_chat_history_messages`
- [ ] Test: `test_send_chat_history_messages_all_filtered_still_calls_core_service`
- [ ] Tests verify correct method calls with `assert_called_once()`
- [ ] Tests verify correct arguments passed to core service

**Technical Guidance:**
- **File:** `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`
- **Reference:** See `TestSuccessPath` in OpenAI extension tests
- **Reference:** See delegation tests in Agent Framework tests
- **Pattern:** Mock core service, verify delegation, check arguments

**Estimated Time:** 3-4 hours

---

### TASK-011: Implement Error Handling Tests

**Title:** Write unit tests for error handling scenarios

**Description:**
Implement unit tests that verify proper error handling for Azure SDK errors, HTTP errors, and unexpected exceptions.

**Acceptance Criteria:**
- [ ] Test class: `TestErrorHandling`
- [ ] Test: `test_send_chat_history_messages_handles_core_service_failure`
- [ ] Test: `test_send_chat_history_messages_handles_unexpected_exception`
- [ ] Test: `test_send_chat_history_handles_api_error`
- [ ] Test: `test_send_chat_history_handles_connection_error`
- [ ] Test: `test_send_chat_history_handles_timeout`
- [ ] Test: `test_send_chat_history_propagates_validation_error`
- [ ] Tests verify `OperationResult.succeeded is False` for failures
- [ ] Tests verify error details are captured in `OperationResult.errors`
- [ ] Tests verify `ValueError` exceptions propagate (not wrapped)

**Technical Guidance:**
- **File:** `tests/tooling/extensions/azureaifoundry/services/test_send_chat_history.py`
- **Reference:** See `TestErrorHandling` in OpenAI extension tests
- **Pattern:** Use `side_effect` to simulate exceptions, verify result state

**Estimated Time:** 2-3 hours

---

## Phase 3: Documentation and Quality

### TASK-012: Add Comprehensive Docstrings and Examples

**Title:** Enhance docstrings with examples and complete documentation

**Description:**
Review and enhance all docstrings for the new methods to include comprehensive documentation with usage examples, following Google-style docstring format.

**Acceptance Criteria:**
- [ ] All public methods have complete docstrings
- [ ] Docstrings include: one-line summary, detailed description, Args, Returns, Raises, Example
- [ ] Example code is syntactically correct and runnable
- [ ] Private helper methods have Args and Returns documented
- [ ] Examples show realistic usage patterns with Azure AI Foundry
- [ ] Examples match patterns shown in PRD Section 7.1

**Technical Guidance:**
- **File:** `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/microsoft_agents_a365/tooling/extensions/azureaifoundry/services/mcp_tool_registration_service.py`
- **Reference:** See docstrings in OpenAI extension methods
- **Reference:** See PRD Section 7.1 for example code

**Example Docstring Pattern:**
```python
async def send_chat_history_messages(
    self,
    turn_context: TurnContext,
    messages: Sequence[ThreadMessage],
    tool_options: Optional[ToolOptions] = None,
) -> OperationResult:
    """
    Send Azure AI Foundry chat history messages to the MCP platform.

    This method accepts a sequence of Azure AI Foundry ThreadMessage objects,
    converts them to ChatHistoryMessage format, and sends them to the MCP
    platform for real-time threat protection.

    Args:
        turn_context: TurnContext from the Agents SDK containing conversation info.
        messages: Sequence of Azure AI Foundry ThreadMessage objects to send.
        tool_options: Optional configuration for the request.

    Returns:
        OperationResult indicating success or failure.

    Raises:
        ValueError: If turn_context or messages is None.

    Example:
        >>> service = McpToolRegistrationService()
        >>> messages = await agents_client.messages.list(thread_id=thread_id)
        >>> result = await service.send_chat_history_messages(
        ...     turn_context, list(messages)
        ... )
        >>> if result.succeeded:
        ...     print("Chat history sent successfully")
    """
```

**Estimated Time:** 2 hours

---

### TASK-013: Final Quality Checks and PR Preparation

**Title:** Run quality checks and prepare for code review

**Description:**
Execute all quality checks, verify test coverage, and ensure code meets SDK standards before creating a pull request.

**Acceptance Criteria:**
- [ ] Run `uv run --frozen ruff check .` - no errors
- [ ] Run `uv run --frozen ruff format --check .` - no formatting issues
- [ ] Run `uv run --frozen pytest tests/tooling/extensions/azureaifoundry/ -v` - all tests pass
- [ ] Run `uv run --frozen pytest tests/tooling/extensions/azureaifoundry/ --cov --cov-report=term-missing` - coverage >= 90%
- [ ] Verify copyright headers on all new/modified files
- [ ] Verify no usage of `typing.Any` in code
- [ ] Verify no usage of forbidden keyword "Kairo"
- [ ] Verify type hints on all function parameters and return types
- [ ] Verify async method names do not use `_async` suffix
- [ ] Run full test suite: `uv run --frozen pytest tests/ -v --tb=short -m "not integration"` - no regressions
- [ ] Prepare PR description with summary and test plan

**Technical Guidance:**
- **Reference:** See CLAUDE.md Code Standards section
- **Reference:** See CI workflow in `.github/workflows/ci.yml`
- **Coverage target:** >= 90% as per PRD Section 10.2

**Estimated Time:** 2-3 hours

---

## Testing Strategy

### Test Categories

| Category | Test Count | Priority |
|----------|------------|----------|
| Input Validation | ~8 tests | P0 |
| Message Conversion | ~15 tests | P0 |
| Success Path | ~10 tests | P0 |
| Error Handling | ~6 tests | P1 |

### Mock Strategy

All tests use `unittest.mock` to mock:
- Azure AI Foundry SDK types (`AgentsClient`, `ThreadMessage`, `MessageTextContent`)
- Core service (`McpToolServerConfigurationService`)
- `TurnContext` from Microsoft Agents SDK

### Coverage Requirements

- Minimum 90% line coverage for new code
- All public methods must have tests for:
  - Valid inputs (success path)
  - Invalid inputs (validation errors)
  - Edge cases (empty lists, all filtered)
  - Error conditions (exceptions)

---

## Risks and Considerations

### Technical Risks

| Risk | Mitigation |
|------|------------|
| Azure SDK beta API changes | Pin minimum versions, use defensive coding for optional attributes |
| Async iteration differences | Test both sync and async collection patterns |
| Content structure variations | Handle unknown content types gracefully, log warnings |

### Implementation Notes

1. **Type Hints:** Never use `typing.Any`. Import actual types from Azure SDK or use `object` for truly unknown types.

2. **Async Pattern:** The Azure SDK's `messages.list()` returns an async iterable. Collect to list before processing.

3. **Role Enum:** Azure SDK role is an enum object with `.value` attribute, not a plain string.

4. **Content Structure:** Messages can have multiple content items of different types. Only process `MessageTextContent`.

5. **Naming:** The Azure Python SDK uses `AgentsClient` and `ThreadMessage` (not `PersistentAgentsClient` and `PersistentThreadMessage` as in .NET).

---

## Summary

| Phase | Tasks | Estimated Total Time |
|-------|-------|---------------------|
| Phase 1: Core Implementation | TASK-001 to TASK-005 | 11-16 hours |
| Phase 2: Testing | TASK-006 to TASK-011 | 13-17 hours |
| Phase 3: Documentation & Quality | TASK-012 to TASK-013 | 4-5 hours |
| **Total** | **13 tasks** | **28-38 hours** |

All tasks are designed to be completed by a junior engineer in 2-8 hours each, with clear acceptance criteria and technical guidance. Tasks should be completed in the order specified due to dependencies between them.
