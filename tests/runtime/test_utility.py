# Copyright (c) Microsoft. All rights reserved.

import unittest
import uuid
import jwt

from microsoft_agents_a365.runtime.utility import Utility


class TestUtility(unittest.TestCase):
    """Test cases for the Utility class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_app_id = "12345678-1234-1234-1234-123456789abc"
        self.test_azp_id = "87654321-4321-4321-4321-cba987654321"

    def create_test_jwt(self, claims: dict) -> str:
        """Create a test JWT token with the given claims."""
        # Use PyJWT to create a proper JWT token (unsigned for testing)
        return jwt.encode(claims, key="", algorithm="none")

    def test_get_app_id_from_token_with_none_token(self):
        """Test get_app_id_from_token with None token."""
        result = Utility.get_app_id_from_token(None)
        self.assertEqual(result, str(uuid.UUID(int=0)))

    def test_get_app_id_from_token_with_empty_token(self):
        """Test get_app_id_from_token with empty token."""
        result = Utility.get_app_id_from_token("")
        self.assertEqual(result, str(uuid.UUID(int=0)))

        result = Utility.get_app_id_from_token("   ")
        self.assertEqual(result, str(uuid.UUID(int=0)))

    def test_get_app_id_from_token_with_appid_claim(self):
        """Test get_app_id_from_token with appid claim."""
        token = self.create_test_jwt({"appid": self.test_app_id, "other": "value"})
        result = Utility.get_app_id_from_token(token)
        self.assertEqual(result, self.test_app_id)

    def test_get_app_id_from_token_with_azp_claim(self):
        """Test get_app_id_from_token with azp claim."""
        token = self.create_test_jwt({"azp": self.test_azp_id, "other": "value"})
        result = Utility.get_app_id_from_token(token)
        self.assertEqual(result, self.test_azp_id)

    def test_get_app_id_from_token_with_both_claims(self):
        """Test get_app_id_from_token with both appid and azp claims (appid takes precedence)."""
        token = self.create_test_jwt({"appid": self.test_app_id, "azp": self.test_azp_id})
        result = Utility.get_app_id_from_token(token)
        self.assertEqual(result, self.test_app_id)

    def test_get_app_id_from_token_without_app_claims(self):
        """Test get_app_id_from_token with token containing no app claims."""
        token = self.create_test_jwt({"sub": "user123", "iss": "issuer"})
        result = Utility.get_app_id_from_token(token)
        self.assertEqual(result, "")

    def test_get_app_id_from_token_with_invalid_token(self):
        """Test get_app_id_from_token with invalid token formats."""
        # Invalid token format
        result = Utility.get_app_id_from_token("invalid.token")
        self.assertEqual(result, "")

        # Token with only two parts
        result = Utility.get_app_id_from_token("header.payload")
        self.assertEqual(result, "")

        # Token with invalid base64
        result = Utility.get_app_id_from_token("invalid.!!!invalid!!!.signature")
        self.assertEqual(result, "")


class MockActivity:
    """Mock activity class for testing."""

    def __init__(self, is_agentic: bool = False, agentic_id: str = ""):
        self._is_agentic = is_agentic
        self._agentic_id = agentic_id

    def is_agentic_request(self) -> bool:
        return self._is_agentic

    def get_agentic_instance_id(self) -> str:
        return self._agentic_id


class MockContext:
    """Mock context class for testing."""

    def __init__(self, activity=None):
        self.activity = activity


class TestUtilityResolveAgentIdentity(unittest.TestCase):
    """Test cases for the resolve_agent_identity method."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_app_id = "token-app-id-123"
        self.agentic_id = "agentic-id-456"

        # Create a test token with PyJWT
        claims = {"appid": self.test_app_id}
        self.test_token = jwt.encode(claims, key="", algorithm="none")

    def test_resolve_agent_identity_with_agentic_request(self):
        """Test resolve_agent_identity with agentic request."""
        activity = MockActivity(is_agentic=True, agentic_id=self.agentic_id)
        context = MockContext(activity)

        result = Utility.resolve_agent_identity(context, self.test_token)
        self.assertEqual(result, self.agentic_id)

    def test_resolve_agent_identity_with_non_agentic_request(self):
        """Test resolve_agent_identity with non-agentic request."""
        activity = MockActivity(is_agentic=False)
        context = MockContext(activity)

        result = Utility.resolve_agent_identity(context, self.test_token)
        self.assertEqual(result, self.test_app_id)

    def test_resolve_agent_identity_with_context_without_activity(self):
        """Test resolve_agent_identity with context that has no activity."""
        context = MockContext()

        result = Utility.resolve_agent_identity(context, self.test_token)
        self.assertEqual(result, self.test_app_id)

    def test_resolve_agent_identity_with_none_context(self):
        """Test resolve_agent_identity with None context."""
        result = Utility.resolve_agent_identity(None, self.test_token)
        self.assertEqual(result, self.test_app_id)

    def test_resolve_agent_identity_with_agentic_but_empty_id(self):
        """Test resolve_agent_identity with agentic request but empty agentic ID."""
        activity = MockActivity(is_agentic=True, agentic_id="")
        context = MockContext(activity)

        result = Utility.resolve_agent_identity(context, self.test_token)
        self.assertEqual(result, "")

    def test_resolve_agent_identity_fallback_on_exception(self):
        """Test resolve_agent_identity falls back to token when context access fails."""

        # Create a context that will raise an exception when accessed
        class FaultyContext:
            @property
            def activity(self):
                raise RuntimeError("Context access failed")

        context = FaultyContext()
        result = Utility.resolve_agent_identity(context, self.test_token)
        self.assertEqual(result, self.test_app_id)


if __name__ == "__main__":
    unittest.main()
