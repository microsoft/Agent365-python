# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from os import environ
from setuptools import setup

# Get version from environment variable set by CI/CD
# This will be set by setuptools-git-versioning in the CI pipeline
package_version = environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")

setup(
    version=package_version,
)
