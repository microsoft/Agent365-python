# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
from os import environ
from pathlib import Path

from setuptools import setup

# Get version from environment variable set by CI/CD
package_version = environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")

# Add versioning helper to path
helper_path = Path(__file__).parent.parent.parent / "versioning" / "helper"
sys.path.insert(0, str(helper_path))

from setup_utils import get_dynamic_dependencies  # noqa: E402

# Use exact version matching for internal dependencies:
# - Internal packages get: == current_version (e.g., == 1.2.3)
# - Ensures all SDK packages must be at the same version
# - Prevents incompatibility issues from version mismatches
setup(
    version=package_version,
    install_requires=get_dynamic_dependencies(
        use_exact_match=True,
    ),
)
