# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
from pathlib import Path
from os import environ
from setuptools import setup

# Get version from environment variable set by CI/CD
package_version = environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")

# Add versioning helper to path
helper_path = Path(__file__).parent.parent.parent / "versioning" / "helper"
sys.path.insert(0, str(helper_path))

from setup_utils import get_dynamic_dependencies

# Use minimum version strategy:
# - Internal packages get: >= current_base_version (e.g., >= 0.1.0)
# - Automatically updates when you build new versions
# - Consumers can upgrade to any higher version
setup(
    version=package_version,
    install_requires=get_dynamic_dependencies(
        use_compatible_release=False,  # No upper bound
        use_exact_match=False,  # Not exact match
    ),
)
