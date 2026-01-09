# Copyright (c) Microsoft. All rights reserved.

"""
Utility logic for environment-related operations.
"""

import os

# Authentication scopes for different environments
PROD_OBSERVABILITY_SCOPE = "https://api.powerplatform.com/.default"

# Cluster categories for different environments
PROD_OBSERVABILITY_CLUSTER_CATEGORY = "prod"

# Default environment names
PRODUCTION_ENVIRONMENT_NAME = "production"
DEVELOPMENT_ENVIRONMENT_NAME = "Development"


def get_observability_authentication_scope() -> list[str]:
    """
    Returns the scope for authenticating to the observability service based on the current environment.

    The scope can be overridden via the A365_OBSERVABILITY_SCOPE_OVERRIDE environment variable
    to enable testing against pre-production environments.

    Returns:
        list[str]: The authentication scope for the current environment.
    """
    override_scope = os.getenv("A365_OBSERVABILITY_SCOPE_OVERRIDE", "").strip()
    return [override_scope] if override_scope else [PROD_OBSERVABILITY_SCOPE]


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
