# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fixtures for LangChain observability integration tests."""

import os
from pathlib import Path
from typing import Any

import pytest

try:
    from dotenv import load_dotenv

    current_file = Path(__file__)
    tests_dir = current_file.parent.parent.parent.parent.parent
    env_file = tests_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def pytest_configure(config: pytest.Config) -> None:
    """Add integration marker."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


@pytest.fixture(scope="session")
def azure_openai_config() -> dict[str, Any]:
    """Azure OpenAI configuration for integration tests."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    if not api_key or not endpoint:
        pytest.skip("Integration tests require AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "deployment": deployment,
        "api_version": api_version,
    }


@pytest.fixture(scope="session")
def agent365_config() -> dict[str, Any]:
    """Microsoft Agent 365 configuration for integration tests."""
    tenant_id = os.getenv("AGENT365_TEST_TENANT_ID", "4d44f041-f91e-4d00-b107-61e47b26f5a8")
    agent_id = os.getenv("AGENT365_TEST_AGENT_ID", "3bccd52b-daaa-4b11-af40-47443852137c")

    if not tenant_id:
        pytest.skip("Integration tests require AGENT365_TEST_TENANT_ID")

    return {"tenant_id": tenant_id, "agent_id": agent_id}
