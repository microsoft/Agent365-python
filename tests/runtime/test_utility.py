# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for Utility class."""

import platform
import re
import uuid
from unittest.mock import Mock

import jwt
import pytest
from microsoft_agents_a365.runtime.utility import Utility


# Fixtures (Mocks and Helpers)
@pytest.fixture
def create_test_jwt():
    """Fixture to create test JWT tokens."""

    def _create(claims: dict) -> str:
        return jwt.encode(claims, key="", algorithm="none")

    return _create


@pytest.fixture
def mock_activity():
    """Fixture to create mock activity."""

    def _create(is_agentic=False, agentic_id=""):
        activity = Mock()
        activity.is_agentic_request.return_value = is_agentic
        activity.get_agentic_instance_id.return_value = agentic_id
        return activity

    return _create


@pytest.fixture
def mock_context():
    """Fixture to create mock context."""

    def _create(activity=None):
        context = Mock()
        context.activity = activity
        return context

    return _create


# Tests for get_app_id_from_token
@pytest.mark.parametrize(
    "token,expected",
    [
        (None, str(uuid.UUID(int=0))),
        ("", str(uuid.UUID(int=0))),
        ("   ", str(uuid.UUID(int=0))),
        ("invalid.token", ""),
    ],
)
def test_get_app_id_from_token_invalid(token, expected):
    """Test get_app_id_from_token handles invalid tokens correctly."""
    result = Utility.get_app_id_from_token(token)
    assert result == expected


@pytest.mark.parametrize(
    "claims,expected",
    [
        ({"appid": "test-app-id"}, "test-app-id"),
        ({"azp": "azp-app-id"}, "azp-app-id"),
        ({"appid": "appid-value", "azp": "azp-value"}, "appid-value"),
        ({"sub": "user123"}, ""),
    ],
)
def test_get_app_id_from_token_valid_tokens(create_test_jwt, claims, expected):
    """Test get_app_id_from_token with valid tokens and various claims."""
    token = create_test_jwt(claims)
    result = Utility.get_app_id_from_token(token)
    assert result == expected


# Tests for resolve_agent_identity
@pytest.mark.parametrize(
    "is_agentic,agentic_id,expected",
    [
        (True, "agentic-id", "agentic-id"),
        (True, "", ""),
        (False, "", "token-app-id"),
        (False, "ignored-id", "token-app-id"),
    ],
)
def test_resolve_agent_identity_with_context(
    create_test_jwt, mock_activity, mock_context, is_agentic, agentic_id, expected
):
    """Test resolve_agent_identity returns correct ID based on context."""
    token = create_test_jwt({"appid": "token-app-id"})
    activity = mock_activity(is_agentic=is_agentic, agentic_id=agentic_id)
    context = mock_context(activity)

    result = Utility.resolve_agent_identity(context, token)
    assert result == expected


@pytest.mark.parametrize(
    "context",
    [
        None,
        Mock(activity=None),
    ],
)
def test_resolve_agent_identity_fallback(create_test_jwt, context):
    """Test resolve_agent_identity falls back to token when context is invalid."""
    token = create_test_jwt({"appid": "token-app-id"})
    result = Utility.resolve_agent_identity(context, token)
    assert result == "token-app-id"


def test_resolve_agent_identity_exception_handling(create_test_jwt, mock_context):
    """Test resolve_agent_identity falls back to token when activity methods raise exceptions."""
    token = create_test_jwt({"appid": "token-app-id"})
    activity = Mock()
    activity.is_agentic_request.side_effect = AttributeError("Method not available")
    context = mock_context(activity)

    result = Utility.resolve_agent_identity(context, token)
    assert result == "token-app-id"


def test_get_user_agent_header_default():
    """Test get_user_agent_header returns expected format with default orchestrator."""
    os_type = platform.system()
    py_version = platform.python_version()

    result = Utility.get_user_agent_header()

    # Regex for Agent365SDK/version (OS; Python version)
    pattern = rf"^Agent365SDK/.+ \({os_type}; Python {py_version}\)$"
    assert re.match(pattern, result)


def test_get_user_agent_header_with_orchestrator():
    """Test get_user_agent_header includes orchestrator when provided."""
    orchestrator = "TestOrchestrator"
    os_type = platform.system()
    py_version = platform.python_version()

    result = Utility.get_user_agent_header(orchestrator)

    # Regex for Agent365SDK/version (OS; Python version; TestOrchestrator)
    pattern = rf"^Agent365SDK/.+ \({os_type}; Python {py_version}; {orchestrator}\)$"
    assert re.match(pattern, result)
