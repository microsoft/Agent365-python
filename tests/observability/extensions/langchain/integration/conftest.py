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
