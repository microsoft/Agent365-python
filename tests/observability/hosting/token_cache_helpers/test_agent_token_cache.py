# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for AgenticTokenCache and AgenticTokenStruct."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from microsoft_agents.hosting.core.app.oauth.authorization import Authorization
from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.observability.hosting.token_cache_helpers import (
    AgenticTokenCache,
    AgenticTokenStruct,
)


@pytest.fixture
def mock_authorization():
    """Create a mock Authorization instance."""
    auth = MagicMock(spec=Authorization)
    auth.exchange_token = AsyncMock()
    return auth


@pytest.fixture
def mock_turn_context():
    """Create a mock TurnContext instance."""
    return MagicMock(spec=TurnContext)


@pytest.fixture
def token_cache():
    """Create a fresh AgenticTokenCache instance."""
    return AgenticTokenCache()


@pytest.mark.asyncio
async def test_register_and_retrieve_token_success(
    token_cache, mock_authorization, mock_turn_context
):
    """Test complete flow: create struct, register, and retrieve token successfully."""
    agent_id = "agent-123"
    tenant_id = "tenant-456"
    expected_token = "mock-token-xyz"
    scopes = ["https://example.com/.default"]

    mock_authorization.exchange_token.return_value = expected_token

    token_struct = AgenticTokenStruct(
        authorization=mock_authorization,
        turn_context=mock_turn_context,
    )
    assert token_struct.auth_handler_name == "AGENTIC"

    token_cache.register_observability(
        agent_id=agent_id,
        tenant_id=tenant_id,
        token_generator=token_struct,
        observability_scopes=scopes,
    )

    token = await token_cache.get_observability_token(agent_id, tenant_id)
    assert token == expected_token


@pytest.mark.parametrize(
    "agent_id,tenant_id,token_generator,error_type,error_match",
    [
        ("", "tenant-456", "valid", ValueError, "agent_id cannot be None or whitespace"),
        ("agent-123", "tenant-456", None, TypeError, "token_generator cannot be None"),
    ],
)
def test_register_observability_validation(
    token_cache,
    mock_authorization,
    mock_turn_context,
    agent_id,
    tenant_id,
    token_generator,
    error_type,
    error_match,
):
    """Test that registration validates inputs and raises appropriate errors."""
    struct = None
    if token_generator == "valid":
        struct = AgenticTokenStruct(
            authorization=mock_authorization,
            turn_context=mock_turn_context,
        )

    with pytest.raises(error_type, match=error_match):
        token_cache.register_observability(
            agent_id=agent_id,
            tenant_id=tenant_id,
            token_generator=struct,
            observability_scopes=["scope"],
        )


def test_thread_safety(token_cache, mock_authorization, mock_turn_context):
    """Test that cache is thread-safe with concurrent registrations."""
    import threading

    agent_id = "agent-123"
    tenant_id = "tenant-456"
    results = []

    def register_token(scope_suffix):
        try:
            struct = AgenticTokenStruct(
                authorization=mock_authorization,
                turn_context=mock_turn_context,
            )
            token_cache.register_observability(
                agent_id=agent_id,
                tenant_id=tenant_id,
                token_generator=struct,
                observability_scopes=[f"scope-{scope_suffix}"],
            )
            results.append(scope_suffix)
        except Exception as e:
            results.append(f"error: {e}")

    # Create 10 concurrent registrations
    threads = [threading.Thread(target=register_token, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All registrations should succeed
    assert len(results) == 10
    # Only one entry should exist (idempotent)
    assert f"{agent_id}:{tenant_id}" in token_cache._map
