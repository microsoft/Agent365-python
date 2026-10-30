# Test Plan for Agent365-Python SDK

> **Note:** This plan is under active development. Keep updating as testing progresses.

**Version:** 1.0  
**Date:** November 24, 2025  
**Status:** Draft

---

## Overview

### Current State
- ✅ Unit tests exist for `runtime` modules; observability has [moved out of this repository](../docs/observability-migration.md)
- ❌ Missing tests for `tooling` and `notifications` modules
- ❌ No integration tests or CI/CD automation

### Goals
- Achieve **80%+ code coverage** across all modules
- Implement integration tests for cross-module functionality
- Integrate testing into CI/CD pipeline with coverage enforcement

---

## Testing Strategy

**Framework:** `pytest`  
**Coverage:** `pytest-cov`  
**Mocking:** `unittest.mock`  
**Async:** `pytest-asyncio`

**Test Pattern:** AAA (Arrange → Act → Assert)  
**Naming Convention:** `test_<method>_<condition>_<expected_result>`

---

## Implementation Roadmap

| Phase | Deliverables | Priority |
|-------|-------------|----------|
| 1.1 | Runtime unit tests | ✅ Complete |
| 1.2 | Tooling unit tests | HIGH |
| 1.3 | Notifications unit tests | HIGH |
| 1.5 | Tooling extension tests | LOW |
| 2 | Integration tests | MEDIUM |
| 3 | CI/CD automation | HIGH |

---

## Phase 1: Unit Tests

### 1.1 Runtime Module
**Priority:** HIGH

| Module | Test File | Status |
|--------|-----------|--------|
| `power_platform_api_discovery.py` | `test_power_platform_api_discovery.py` | ✅ Complete |
| `utility.py` | `test_utility.py` | ✅ Complete |
| `environment_utils.py` | `test_environment_utils.py` | ✅ Complete |
| `version_utils.py` | `test_version_utils.py` | ✅ Complete |

---

### 1.2 Tooling Module
**Priority:** HIGH

| Module | Test File | Status |
|--------|-----------|--------|
| `utils/utility.py` | `test_utility.py` | ❌ Missing |
| `models/mcp_server_config.py` | `test_mcp_server_config.py` | ❌ Missing |
| `services/mcp_tool_server_configuration_service.py` | `test_mcp_tool_server_configuration_service.py` | ❌ Missing |

---

### 1.3 Notifications Module
**Priority:** HIGH

| Module | Test File | Status |
|--------|-----------|--------|
| `models/agent_lifecycle_event.py` | `test_agent_lifecycle_event.py` | ❌ Missing |
| `models/agent_notification_activity.py` | `test_agent_notification_activity.py` | ❌ Missing |
| `models/email_reference.py` | `test_email_reference.py` | ❌ Missing |
| `agent_notification.py` | `test_agent_notification.py` | ❌ Missing |

---

### 1.5 Tooling Extensions
**Priority:** LOW

| Extension | Status |
|-----------|--------|
| Agent Framework | ❌ Missing |
| Azure AI Foundry | ❌ Missing |
| OpenAI | ❌ Missing |
| Semantic Kernel | ❌ Missing |

---

## Phase 2: Integration Tests

**Priority:** MEDIUM

| Integration | Status |
|-------------|--------|
| Tooling + Runtime | ❌ Missing |
| Notifications + Runtime | ❌ Missing |
| Agent Framework full flow | ❌ Missing |

---

## Phase 3: CI/CD Integration

**Priority:** HIGH

| Component | Status |
|-----------|--------|
| GitHub Actions workflow | ❌ Missing |
| Python matrix (3.9-3.12) | ❌ Missing |
| Coverage enforcement (80%+) | ❌ Missing |
| Codecov integration | ❌ Missing |
| PR blocking on failures | ❌ Missing |

---

## Success Criteria

- ✅ 80%+ code coverage for all modules
- ✅ All tests pass independently
- ✅ Full suite completes in < 30 seconds (unit) / < 5 minutes (full)
- ✅ Automated test execution on all PRs
- ✅ Coverage reports visible and enforced
