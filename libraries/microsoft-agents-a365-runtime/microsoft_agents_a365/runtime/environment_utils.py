# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Utility logic for environment-related operations.
"""

import os

# Default environment names
PRODUCTION_ENVIRONMENT_NAME = "production"
DEVELOPMENT_ENVIRONMENT_NAME = "Development"


def is_development_environment() -> bool:
    """
    Returns True if the current environment is a development environment.

    Returns:
        bool: True if the current environment is development, False otherwise.
    """
    environment = _get_current_environment()
    return environment.lower() == DEVELOPMENT_ENVIRONMENT_NAME.lower()


def _get_current_environment() -> str:
    """
    Gets the current environment name.

    Returns:
        str: The current environment name.
    """
    # Check environment variables in order of precedence

    # Check Python-specific environment variables
    environment = os.getenv("PYTHON_ENVIRONMENT")
    if environment:
        return environment

    # Default to Production
    return PRODUCTION_ENVIRONMENT_NAME
