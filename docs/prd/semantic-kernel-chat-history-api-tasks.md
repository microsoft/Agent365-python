# Task Breakdown: Semantic Kernel Chat History API

## Document Information

| Field | Value |
|-------|-------|
| **PRD Reference** | `docs/prd/semantic-kernel-chat-history-api.md` |
| **Created** | 2026-01-28 |
| **Target Package** | `microsoft-agents-a365-tooling-extensions-semantickernel` |
| **Target Version** | 1.1.0 |

---

## Executive Summary

This document breaks down the implementation of the Send Chat History API for the Semantic Kernel orchestrator extension. The feature enables developers to send conversation history from Semantic Kernel agents to the MCP (Model Context Protocol) platform for real-time threat protection and compliance monitoring.

The implementation follows established patterns from the existing OpenAI extension chat history API, ensuring consistency across orchestrators. The core work involves adding two new public methods (`send_chat_history` and `send_chat_history_messages`) to the existing `McpToolRegistrationService` class, along with private helper methods for message conversion from Semantic Kernel's `ChatMessageContent` type to the common `ChatHistoryMessage` format.

The implementation is scoped as a minor version bump (1.0.0 to 1.1.0) since it adds new functionality without breaking existing APIs. Total estimated effort is 16-24 hours across 8 tasks, suitable for a junior engineer with guidance on the Semantic Kernel SDK specifics.

---

## Architecture Impact

### Packages Affected

| Package | Impact Level | Changes |
|---------|--------------|---------|
| `microsoft-agents-a365-tooling-extensions-semantickernel` | **Primary** | Add chat history methods to `McpToolRegistrationService` |
| `microsoft-agents-a365-tooling` | **None** | Core `send_chat_history` already implemented; no changes needed |
| `microsoft-agents-a365-runtime` | **None** | Uses existing `OperationResult`, `OperationError` |

### Files to Modify

| File Path | Change Type |
|-----------|-------------|
| `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/services/mcp_tool_registration_service.py` | **Modified** - Add chat history methods |
| `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/docs/design.md` | **Modified** - Document chat history API |

### Files to Create

| File Path | Purpose |
|-----------|---------|
| `tests/tooling/extensions/semantickernel/__init__.py` | Test package init |
| `tests/tooling/extensions/semantickernel/services/__init__.py` | Services test subpackage init |
| `tests/tooling/extensions/semantickernel/services/conftest.py` | Pytest fixtures for Semantic Kernel mocks |
| `tests/tooling/extensions/semantickernel/services/test_send_chat_history.py` | Unit tests for chat history API |

---

## Task Breakdown

### Phase 1: Foundation (Tasks 1-2)

#### Task 1: Add Semantic Kernel Imports and Constants

**Description**: Add the necessary imports for Semantic Kernel types and standard library modules required for the chat history implementation. This foundational task prepares the module for the new functionality.

**Package**: `microsoft-agents-a365-tooling-extensions-semantickernel`

**File**: `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/services/mcp_tool_registration_service.py`

**Acceptance Criteria**:
- [ ] Import `uuid` module for generating message IDs
- [ ] Import `datetime` and `timezone` from datetime module
- [ ] Import `Sequence` and `List` from typing module
- [ ] Import `ChatHistory`, `ChatMessageContent`, `AuthorRole` from `semantic_kernel.contents`
- [ ] Import `ChatHistoryMessage`, `ToolOptions` from `microsoft_agents_a365.tooling.models`
- [ ] Import `OperationResult`, `OperationError` from `microsoft_agents_a365.runtime`
- [ ] All imports are placed in correct sections (standard library, third-party, local)
- [ ] File passes `ruff check` linting

**Technical Guidance**:
- Reference the existing imports in the file and maintain the same organization style
- The Semantic Kernel imports should be in the third-party section
- Verify imports compile correctly by running `python -c "from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService"`

**Estimated Time**: 1 hour

---

#### Task 2: Implement Private Helper Methods for Message Conversion

**Description**: Implement the private helper methods that convert Semantic Kernel message types to the common `ChatHistoryMessage` format. These methods handle role mapping, content extraction, ID generation, and timestamp handling.

**Package**: `microsoft-agents-a365-tooling-extensions-semantickernel`

**File**: `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/services/mcp_tool_registration_service.py`

**Acceptance Criteria**:
- [ ] Implement `_map_author_role(self, role: AuthorRole) -> str` that converts AuthorRole enum to lowercase string
- [ ] Implement `_extract_content(self, message: ChatMessageContent) -> str` that extracts text content with type validation
- [ ] Implement `_extract_or_generate_id(self, message: ChatMessageContent, index: int) -> str` that extracts ID from metadata or generates UUID
- [ ] Implement `_extract_or_generate_timestamp(self, message: ChatMessageContent, index: int) -> datetime` that extracts timestamp or uses current UTC
- [ ] Implement `_convert_single_sk_message(self, message: ChatMessageContent, index: int) -> Optional[ChatHistoryMessage]` that converts a single message
- [ ] Implement `_convert_sk_messages_to_chat_history(self, messages: Sequence[ChatMessageContent]) -> List[ChatHistoryMessage]` that converts all messages
- [ ] All methods include appropriate debug/warning logging
- [ ] Methods handle None messages gracefully (skip with warning)
- [ ] Methods handle empty/whitespace content gracefully (skip with warning)
- [ ] **Security**: `_extract_content` returns empty string for unexpected content types (non-string) to prevent sensitive data exposure
- [ ] Copyright header is present at file top

**Technical Guidance**:
- Follow the pattern established in the OpenAI extension's `_convert_single_message` and related methods
- AuthorRole mapping: `role.name.lower()` (USER -> "user", ASSISTANT -> "assistant", etc.)
- Use `message.metadata.get("id")` for existing IDs, `message.metadata.get("timestamp")` for timestamps
- Support timestamp formats: datetime objects, Unix timestamps (int/float), ISO strings
- Place these methods in a section marked `# PRIVATE HELPER METHODS - Message Conversion`
- **Security**: In `_extract_content`, only return content if it's a string; for unexpected types (int, dict, objects), return empty string and log warning to avoid exposing sensitive data via `__str__` or `__repr__`

**Dependencies**: Task 1 (imports must be in place)

**Estimated Time**: 3 hours

---

### Phase 2: Core Implementation (Tasks 3-4)

#### Task 3: Implement send_chat_history_messages Method

**Description**: Implement the public `send_chat_history_messages` method that accepts a sequence of Semantic Kernel `ChatMessageContent` objects and sends them to the MCP platform.

**Package**: `microsoft-agents-a365-tooling-extensions-semantickernel`

**File**: `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/services/mcp_tool_registration_service.py`

**Acceptance Criteria**:
- [ ] Method signature matches PRD specification:
  ```python
  async def send_chat_history_messages(
      self,
      turn_context: TurnContext,
      messages: Sequence[ChatMessageContent],
      options: Optional[ToolOptions] = None,
  ) -> OperationResult:
  ```
- [ ] Validates `turn_context` is not None (raises `ValueError`)
- [ ] Validates `messages` is not None (raises `ValueError`)
- [ ] Empty `messages` list is allowed and still calls core service
- [ ] Sets default `ToolOptions` with `orchestrator_name="SemanticKernel"` if options is None
- [ ] Sets `orchestrator_name="SemanticKernel"` if options provided but `orchestrator_name` is None
- [ ] Calls `_convert_sk_messages_to_chat_history` to convert messages
- [ ] Delegates to `self._mcp_server_configuration_service.send_chat_history()`
- [ ] Re-raises `ValueError` from core service
- [ ] Catches other exceptions and returns `OperationResult.failed(OperationError(ex))`
- [ ] Includes comprehensive logging (INFO at entry/exit, DEBUG for details)
- [ ] Docstring follows Google style with Args, Returns, Raises, and Example sections

**Technical Guidance**:
- Mirror the implementation pattern from OpenAI extension's `send_chat_history_messages`
- Place in section marked `# SEND CHAT HISTORY - Semantic Kernel-specific implementations`
- The core service is available via `self._mcp_server_configuration_service`
- Log INFO: "Sending {count} Semantic Kernel messages as chat history"
- Log INFO on empty list: "Empty chat history messages (either no input or all filtered), still sending to register user message"

**Dependencies**: Task 2 (helper methods must be implemented)

**Estimated Time**: 2 hours

---

#### Task 4: Implement send_chat_history Method

**Description**: Implement the public `send_chat_history` method that accepts a Semantic Kernel `ChatHistory` object and sends its messages to the MCP platform.

**Package**: `microsoft-agents-a365-tooling-extensions-semantickernel`

**File**: `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/services/mcp_tool_registration_service.py`

**Acceptance Criteria**:
- [ ] Method signature matches PRD specification:
  ```python
  async def send_chat_history(
      self,
      turn_context: TurnContext,
      chat_history: ChatHistory,
      limit: Optional[int] = None,
      options: Optional[ToolOptions] = None,
  ) -> OperationResult:
  ```
- [ ] Validates `turn_context` is not None (raises `ValueError`)
- [ ] Validates `chat_history` is not None (raises `ValueError`)
- [ ] Extracts messages via `list(chat_history.messages)`
- [ ] Applies `limit` parameter correctly (takes most recent N messages with `messages[-limit:]`)
- [ ] Logs when limit is applied: "Applying limit of {limit} to {total} messages"
- [ ] Delegates to `send_chat_history_messages` method
- [ ] Re-raises `ValueError` exceptions
- [ ] Catches other exceptions and returns `OperationResult.failed(OperationError(ex))`
- [ ] Docstring follows Google style with Args, Returns, Raises, and Example sections

**Technical Guidance**:
- Mirror the implementation pattern from OpenAI extension's `send_chat_history`
- The `limit` logic should slice from the end: `messages[-limit:]` to get most recent
- This method should be placed before `send_chat_history_messages` in the file

**Dependencies**: Task 3 (send_chat_history_messages must be implemented)

**Estimated Time**: 1.5 hours

---

### Phase 3: Testing (Tasks 5-7)

#### Task 5: Create Test Infrastructure and Fixtures

**Description**: Set up the test directory structure and create pytest fixtures for mocking Semantic Kernel types and the TurnContext.

**Package**: Tests

**Files to Create**:
- `tests/tooling/extensions/semantickernel/__init__.py`
- `tests/tooling/extensions/semantickernel/services/__init__.py`
- `tests/tooling/extensions/semantickernel/services/conftest.py`

**Acceptance Criteria**:
- [ ] Create `__init__.py` files with copyright headers
- [ ] Create mock classes in conftest.py:
  - `MockChatMessageContent` - Mock Semantic Kernel message with role, content, metadata
  - `MockChatHistory` - Mock ChatHistory with messages property
  - `MockAuthorRole` - Enum-like mock for USER, ASSISTANT, SYSTEM, TOOL roles
- [ ] Create pytest fixtures:
  - `mock_turn_context` - Valid TurnContext mock
  - `mock_turn_context_no_activity` - TurnContext with no activity
  - `mock_turn_context_no_conversation_id` - TurnContext with no conversation ID
  - `mock_turn_context_no_message_id` - TurnContext with no message ID
  - `mock_turn_context_no_user_message` - TurnContext with no user message text
  - `mock_chat_history` - ChatHistory mock with sample messages
  - `mock_empty_chat_history` - ChatHistory mock with no messages
  - `sample_sk_messages` - List of mock ChatMessageContent objects
  - `sample_sk_messages_with_metadata` - Messages with IDs and timestamps in metadata
  - `service` - McpToolRegistrationService instance
  - `mock_config_service` - AsyncMock for McpToolServerConfigurationService
- [ ] All fixtures include appropriate type hints
- [ ] conftest.py includes copyright header

**Technical Guidance**:
- Reference `tests/tooling/extensions/openai/conftest.py` for fixture patterns
- Use `unittest.mock.Mock` and `unittest.mock.AsyncMock`
- The service fixture should inject the mock_config_service
- AuthorRole mock should have a `name` property that returns uppercase strings

**Dependencies**: None (can be done in parallel with Tasks 1-4)

**Estimated Time**: 2.5 hours

---

#### Task 6: Implement Unit Tests for Input Validation

**Description**: Write unit tests for input validation in both `send_chat_history` and `send_chat_history_messages` methods.

**Package**: Tests

**File**: `tests/tooling/extensions/semantickernel/services/test_send_chat_history.py`

**Acceptance Criteria**:
- [ ] Test class `TestInputValidation` with tests:
  - `test_send_chat_history_validates_turn_context_none` - Raises ValueError
  - `test_send_chat_history_validates_chat_history_none` - Raises ValueError
  - `test_send_chat_history_messages_validates_turn_context_none` - Raises ValueError
  - `test_send_chat_history_messages_validates_messages_none` - Raises ValueError
  - `test_send_chat_history_messages_empty_list_calls_core_service` - Empty list still calls service
  - `test_send_chat_history_messages_whitespace_only_messages_filtered` - Messages with whitespace content are filtered
- [ ] All tests marked with `@pytest.mark.asyncio` and `@pytest.mark.unit`
- [ ] Tests use fixtures from conftest.py
- [ ] Tests verify exact error messages where applicable
- [ ] File includes copyright header

**Technical Guidance**:
- Follow the test patterns in `tests/tooling/extensions/openai/test_send_chat_history.py`
- Use `pytest.raises(ValueError, match="...")` for validation tests
- Test IDs should follow pattern: UV-01, UV-02, etc.

**Dependencies**: Task 5 (fixtures must be available)

**Estimated Time**: 2 hours

---

#### Task 7: Implement Unit Tests for Message Conversion and Success Paths

**Description**: Write unit tests for message conversion logic, role mapping, and successful execution paths.

**Package**: Tests

**File**: `tests/tooling/extensions/semantickernel/services/test_send_chat_history.py`

**Acceptance Criteria**:
- [ ] Test class `TestRoleMapping` with parameterized test:
  - `test_map_author_role_converts_to_lowercase` - Parameterized for USER/user, ASSISTANT/assistant, SYSTEM/system, TOOL/tool
- [ ] Test class `TestMessageConversion` with tests:
  - `test_convert_single_sk_message_user_message` - Converts user message correctly
  - `test_convert_single_sk_message_assistant_message` - Converts assistant message correctly
  - `test_convert_single_sk_message_system_message` - Converts system message correctly
  - `test_convert_single_sk_message_skips_null_message` - Returns None for null input
  - `test_convert_single_sk_message_skips_empty_content` - Returns None for empty content
  - `test_convert_single_sk_message_skips_whitespace_content` - Returns None for whitespace-only
  - `test_convert_single_sk_message_extracts_id_from_metadata` - Uses existing ID
  - `test_convert_single_sk_message_generates_id_when_missing` - Generates UUID
  - `test_convert_single_sk_message_extracts_timestamp_from_metadata` - Uses existing timestamp
  - `test_convert_single_sk_message_generates_timestamp_when_missing` - Uses current UTC
  - `test_convert_sk_messages_filters_invalid` - Batch conversion filters invalid messages
- [ ] Test class `TestSuccessPath` with tests:
  - `test_send_chat_history_messages_success` - Returns OperationResult.success()
  - `test_send_chat_history_messages_with_options` - Custom options passed through
  - `test_send_chat_history_messages_default_orchestrator_name` - Default is "SemanticKernel"
  - `test_send_chat_history_success` - ChatHistory object processed correctly
  - `test_send_chat_history_with_limit` - Limit parameter works correctly
  - `test_send_chat_history_delegates_to_send_chat_history_messages` - Delegation verified
- [ ] Test class `TestLimitFunctionality` with tests:
  - `test_send_chat_history_limit_takes_most_recent` - Last N messages taken
  - `test_send_chat_history_limit_larger_than_messages` - All messages sent if limit > count
  - `test_send_chat_history_no_limit_sends_all` - All messages sent without limit
  - `test_send_chat_history_limit_zero_sends_all` - Zero limit treated as no limit
- [ ] All tests marked with `@pytest.mark.asyncio` and `@pytest.mark.unit`
- [ ] File includes copyright header

**Technical Guidance**:
- Use `@pytest.mark.parametrize` for role mapping tests
- Verify UUID format with `uuid.UUID(result.id)` - will raise if invalid
- Use time comparison `before <= result.timestamp <= after` for generated timestamps
- Patch `service._mcp_server_configuration_service.send_chat_history` to verify delegation

**Dependencies**: Task 5 (fixtures), Task 6 (can be same file)

**Estimated Time**: 3 hours

---

#### Task 8: Implement Unit Tests for Error Handling

**Description**: Write unit tests for error handling scenarios including HTTP errors, timeouts, and conversion failures.

**Package**: Tests

**File**: `tests/tooling/extensions/semantickernel/services/test_send_chat_history.py`

**Acceptance Criteria**:
- [ ] Test class `TestErrorHandling` with tests:
  - `test_send_chat_history_messages_http_error` - Returns OperationResult.failed()
  - `test_send_chat_history_messages_timeout_error` - Returns OperationResult.failed()
  - `test_send_chat_history_messages_client_error` - Returns OperationResult.failed()
  - `test_send_chat_history_messages_conversion_error` - Handles gracefully
  - `test_send_chat_history_messages_core_service_value_error` - Re-raises ValueError
  - `test_send_chat_history_extraction_error` - Handles ChatHistory.messages access errors
- [ ] Test class `TestOrchestratorNameHandling` with tests:
  - `test_options_with_none_orchestrator_name_gets_default` - Sets "SemanticKernel"
  - `test_options_preserves_custom_orchestrator_name` - Custom name preserved
- [ ] All tests verify error details are captured in OperationResult
- [ ] All tests marked with `@pytest.mark.asyncio` and `@pytest.mark.unit`

**Technical Guidance**:
- Import `aiohttp` for `aiohttp.ClientError` testing
- Use `mock_config_service.send_chat_history.side_effect` to simulate errors
- Verify `result.succeeded is False` and `len(result.errors) == 1` for failure cases

**Dependencies**: Task 5 (fixtures), Tasks 6-7 (same test file)

**Estimated Time**: 2 hours

---

### Phase 4: Documentation and Polish (Task 9)

#### Task 9: Update Documentation and Version

**Description**: Update the package design documentation with chat history API examples and update the package version to 1.1.0.

**Package**: `microsoft-agents-a365-tooling-extensions-semantickernel`

**Files**:
- `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/docs/design.md`
- `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/microsoft_agents_a365/tooling/extensions/semantickernel/__init__.py`

**Acceptance Criteria**:
- [ ] design.md updated with new section: "### Chat History API"
- [ ] design.md includes usage example for `send_chat_history` method
- [ ] design.md includes usage example for `send_chat_history_messages` method
- [ ] design.md documents the message conversion flow
- [ ] `__init__.py` exports remain unchanged (class already exported)
- [ ] Run `ruff check` and `ruff format` on modified files
- [ ] Run `pytest tests/tooling/extensions/semantickernel/ -v` - all tests pass
- [ ] Run `pytest tests/tooling/extensions/semantickernel/ --cov` - coverage >= 90%

**Technical Guidance**:
- Follow the documentation pattern established in the OpenAI extension design.md
- Include a sequence diagram showing the flow from ChatHistory to MCP platform
- Version bump happens automatically via `AGENT365_PYTHON_SDK_PACKAGE_VERSION` env var at build time

**Dependencies**: All previous tasks completed

**Estimated Time**: 2 hours

---

## Task Dependencies

```
Phase 1: Foundation
    Task 1 (Imports) ──────────────┐
                                   │
    Task 2 (Helper Methods) ◄──────┘
           │
           │
Phase 2: Core Implementation
           ▼
    Task 3 (send_chat_history_messages)
           │
           ▼
    Task 4 (send_chat_history)
           │
           │
Phase 3: Testing (can start in parallel with Phase 2)
           │
    Task 5 (Test Infrastructure) ◄─────── Independent
           │
           ├─────────────────┬────────────────┐
           ▼                 ▼                ▼
    Task 6 (Validation)  Task 7 (Conversion)  Task 8 (Errors)
           │                 │                │
           └─────────────────┴────────────────┘
                             │
Phase 4: Documentation       │
                             ▼
                    Task 9 (Docs & Polish)
```

### Parallel Execution Opportunities

- **Tasks 1-2** can run sequentially (Task 2 depends on Task 1)
- **Task 5** can run in parallel with Tasks 1-4 (test infrastructure is independent)
- **Tasks 6, 7, 8** can run in parallel after Task 5 is complete
- **Task 9** must wait for all other tasks

---

## Testing Strategy

### Test Categories

| Category | Test Count | Coverage Target |
|----------|------------|-----------------|
| Input Validation | 6 | 100% of validation code paths |
| Role Mapping | 1 (parameterized, 4 cases) | 100% of role values |
| Message Conversion | 11 | 100% of conversion logic |
| Success Paths | 6 | All happy path scenarios |
| Limit Functionality | 4 | All limit edge cases |
| Error Handling | 6 | All error scenarios |
| Orchestrator Name | 2 | Options handling |

**Total Estimated Tests**: ~36 test cases

### Test Markers

All tests should use these pytest markers:

```python
@pytest.mark.asyncio  # For async test methods
@pytest.mark.unit     # For fast unit tests (no I/O)
```

### Running Tests

```bash
# Run all Semantic Kernel extension tests
pytest tests/tooling/extensions/semantickernel/ -v

# Run with coverage
pytest tests/tooling/extensions/semantickernel/ --cov=libraries/microsoft-agents-a365-tooling-extensions-semantickernel --cov-report=html

# Run only unit tests
pytest tests/tooling/extensions/semantickernel/ -m unit -v
```

---

## Risks and Considerations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Semantic Kernel SDK type changes | Low | Medium | Pin minimum version `>=1.0.0`, test against multiple versions |
| AuthorRole enum has different values than expected | Low | Low | Use defensive `role.name.lower()` with try/except fallback |
| ChatHistory.messages property behavior differs | Medium | Medium | Wrap in `list()` call, add explicit tests |
| Metadata structure inconsistent across SK versions | Medium | Low | Use `.get()` with defaults, don't assume structure |

### Areas Requiring Senior Review

No outstanding items requiring senior review.

**Resolved Items:**
- ~~Message Filtering Logic~~: Confirmed as intentional - messages with empty content are skipped (not failed)
- ~~TOOL Role Handling~~: Confirmed that `ChatHistoryMessage.role` is a string with no limitations; any role value passes through
- ~~Performance with Large Chat Histories~~: The `limit` parameter addresses this; no specific recommendation at this time

### Code Quality Checklist

Before PR submission, verify:

- [ ] All files have copyright header
- [ ] All public methods have Google-style docstrings with examples
- [ ] Type hints on all method parameters and return values
- [ ] `ruff check .` passes with no errors
- [ ] `ruff format .` applied
- [ ] Test coverage >= 90%
- [ ] All tests pass on Python 3.11 and 3.12

---

## Appendix: Reference Code Snippets

### Example: AuthorRole Mapping

```python
def _map_author_role(self, role: AuthorRole) -> str:
    """Map Semantic Kernel AuthorRole enum to lowercase string."""
    return role.name.lower()
```

### Example: ID Extraction with Fallback

```python
def _extract_or_generate_id(self, message: ChatMessageContent, index: int) -> str:
    """Extract message ID from metadata or generate UUID."""
    if message.metadata and "id" in message.metadata:
        existing_id = message.metadata["id"]
        if existing_id:
            return str(existing_id)

    generated_id = str(uuid.uuid4())
    self._logger.debug(f"Generated UUID {generated_id} for message at index {index}")
    return generated_id
```

### Example: Test Fixture

```python
@pytest.fixture
def mock_chat_message_content():
    """Factory fixture for creating mock ChatMessageContent."""
    def _create(
        role_name: str = "USER",
        content: str = "Test message",
        metadata: dict | None = None,
    ):
        message = Mock()
        message.role = Mock()
        message.role.name = role_name
        message.content = content
        message.metadata = metadata or {}
        return message
    return _create
```
