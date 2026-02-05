# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for Utility class."""

import os
import platform
import re
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

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


@pytest.fixture(autouse=True)
def reset_application_name_cache():
    """Reset the application name cache before each test."""
    Utility.reset_application_name_cache()
    yield
    Utility.reset_application_name_cache()


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


# Tests for get_agent_id_from_token
class TestGetAgentIdFromToken:
    """Tests for the get_agent_id_from_token method."""

    def test_empty_token_returns_empty_string(self):
        """Test that empty token returns empty string (not default GUID)."""
        assert Utility.get_agent_id_from_token("") == ""

    def test_none_token_returns_empty_string(self):
        """Test that None token returns empty string."""
        assert Utility.get_agent_id_from_token(None) == ""

    def test_whitespace_token_returns_empty_string(self):
        """Test that whitespace-only token returns empty string."""
        assert Utility.get_agent_id_from_token("   ") == ""

    def test_xms_par_app_azp_takes_highest_priority(self, create_test_jwt):
        """Test xms_par_app_azp claim takes priority over appid and azp."""
        token = create_test_jwt({
            "xms_par_app_azp": "blueprint-id-123",
            "appid": "app-id-456",
            "azp": "azp-id-789",
        })
        result = Utility.get_agent_id_from_token(token)
        assert result == "blueprint-id-123"

    def test_appid_takes_priority_when_no_xms_par_app_azp(self, create_test_jwt):
        """Test appid claim is used when xms_par_app_azp is not present."""
        token = create_test_jwt({
            "appid": "app-id-456",
            "azp": "azp-id-789",
        })
        result = Utility.get_agent_id_from_token(token)
        assert result == "app-id-456"

    def test_azp_used_when_no_other_claims(self, create_test_jwt):
        """Test azp claim is used when xms_par_app_azp and appid are not present."""
        token = create_test_jwt({"azp": "azp-id-789"})
        result = Utility.get_agent_id_from_token(token)
        assert result == "azp-id-789"

    def test_returns_empty_when_no_relevant_claims(self, create_test_jwt):
        """Test returns empty string when no relevant claims are present."""
        token = create_test_jwt({"sub": "some-subject", "iss": "some-issuer"})
        result = Utility.get_agent_id_from_token(token)
        assert result == ""

    def test_invalid_token_returns_empty_string(self):
        """Test invalid token returns empty string."""
        result = Utility.get_agent_id_from_token("invalid.token")
        assert result == ""

    def test_falls_back_to_appid_when_xms_par_app_azp_is_empty(self, create_test_jwt):
        """Test falls back to appid when xms_par_app_azp is empty string."""
        token = create_test_jwt({
            "xms_par_app_azp": "",
            "appid": "app-id-456",
        })
        result = Utility.get_agent_id_from_token(token)
        assert result == "app-id-456"

    def test_falls_back_to_azp_when_appid_is_also_empty(self, create_test_jwt):
        """Test falls back to azp when both xms_par_app_azp and appid are empty."""
        token = create_test_jwt({
            "xms_par_app_azp": "",
            "appid": "",
            "azp": "azp-id-789",
        })
        result = Utility.get_agent_id_from_token(token)
        assert result == "azp-id-789"


# Tests for get_application_name
class TestGetApplicationName:
    """Tests for the get_application_name method."""

    def test_returns_env_var_when_set(self):
        """Test returns AGENT365_APPLICATION_NAME env var when set."""
        with patch.dict(os.environ, {"AGENT365_APPLICATION_NAME": "my-test-app"}):
            result = Utility.get_application_name()
            assert result == "my-test-app"

    def test_env_var_takes_priority_over_pyproject(self, tmp_path):
        """Test env var takes priority over pyproject.toml."""
        # Create a pyproject.toml with a different name
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pyproject-app-name"')

        with patch.dict(os.environ, {"AGENT365_APPLICATION_NAME": "env-app-name"}):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result == "env-app-name"

    def test_reads_from_pyproject_when_env_not_set(self, tmp_path):
        """Test reads from pyproject.toml when env var is not set."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pyproject-app-name"')

        # Remove env var if set
        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result == "pyproject-app-name"

    def test_caches_pyproject_result(self, tmp_path):
        """Test that pyproject.toml is only read once."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "cached-name"')

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()

                # First call
                result1 = Utility.get_application_name()
                # Modify file (but cache should prevent re-read)
                pyproject.write_text('[project]\nname = "new-name"')
                # Second call should return cached value
                result2 = Utility.get_application_name()

                assert result1 == "cached-name"
                assert result2 == "cached-name"

    def test_returns_none_when_nothing_available(self, tmp_path):
        """Test returns None when no env var and no pyproject.toml."""
        # Use a directory without pyproject.toml
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=empty_dir):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result is None

    def test_handles_pyproject_without_name(self, tmp_path):
        """Test handles pyproject.toml without name field."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "1.0.0"')

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result is None

    def test_handles_pyproject_with_different_sections(self, tmp_path):
        """Test correctly parses name from [project] section only."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.ruff]\nname = "ruff-name"\n\n[project]\nname = "project-name"\n'
        )

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result == "project-name"

    def test_ignores_fields_starting_with_name(self, tmp_path):
        """Test only matches exact 'name' field, not 'name_something'."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname_something = "wrong"\nnamespace = "also-wrong"\nname = "correct"\n'
        )

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result == "correct"

    def test_handles_inline_comments(self, tmp_path):
        """Test ignores inline comments after the value."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-app" # this is a comment\n')

        env = {k: v for k, v in os.environ.items() if k != "AGENT365_APPLICATION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "cwd", return_value=tmp_path):
                Utility.reset_application_name_cache()
                result = Utility.get_application_name()
                assert result == "my-app"
