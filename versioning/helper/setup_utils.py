# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Shared utilities for setup.py files across all Microsoft Agent 365 Python SDK packages.

This module provides helper functions to dynamically set internal package versions
at build time, ensuring all packages in the monorepo use the exact same version.
"""

from os import environ
from typing import List


def get_package_version() -> str:
    """
    Get the package version from environment variable.

    Returns:
        The version string from AGENT365_PYTHON_SDK_PACKAGE_VERSION environment variable,
        or "0.0.0" if not set.
    """
    return environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")


def get_base_version(version_string: str) -> str:
    """
    Extract the base version (major.minor.micro) from a version string,
    removing any dev, alpha, beta, rc, or post-release suffixes.

    Uses the packaging library for robust PEP 440 compliant parsing.

    Examples:
        "0.1.0.dev5" -> "0.1.0"
        "0.2.0" -> "0.2.0"
        "1.0.0a1" -> "1.0.0"
        "1.2.3b2" -> "1.2.3"
        "2.0.0rc1" -> "2.0.0"
        "1.a.3" -> "1.0.3" (handles edge cases correctly)

    Args:
        version_string: Version string to parse

    Returns:
        Base version string in format "major.minor.micro"
    """
    try:
        from packaging.version import Version

        # Parse the version using packaging library (PEP 440 compliant)
        parsed = Version(version_string)

        # Return base release version (major.minor.micro)
        return f"{parsed.major}.{parsed.minor}.{parsed.micro}"
    except Exception:
        # Fallback to simple parsing if packaging fails or isn't available
        # Remove known suffixes (less robust but works for simple cases)
        import re

        # Match version up to dev/alpha/beta/rc suffixes
        match = re.match(r"^(\d+\.\d+\.\d+)", version_string)
        if match:
            return match.group(1)
        # Last resort: return as-is
        return version_string


def get_next_major_version(base_version: str) -> str:
    """
    Calculate the next major version for upper bound in compatible release.

    For 0.x.y versions, increments minor (0.1.0 -> 0.2.0)
    For x.y.z versions where x > 0, increments major (1.2.3 -> 2.0.0)

    Args:
        base_version: Base version string (e.g., "0.1.0" or "1.2.3")

    Returns:
        Next major version string
    """
    try:
        from packaging.version import Version

        parsed = Version(base_version)

        if parsed.major == 0:
            # For 0.x.y, increment minor version (0.1.0 -> 0.2.0)
            return f"{parsed.major}.{parsed.minor + 1}.0"
        else:
            # For x.y.z where x > 0, increment major (1.2.3 -> 2.0.0)
            return f"{parsed.major + 1}.0.0"
    except Exception:
        # Fallback to string parsing
        parts = base_version.split(".")
        if len(parts) >= 3:
            major = int(parts[0])
            if major == 0:
                minor = int(parts[1])
                return f"{major}.{minor + 1}.0"
            else:
                return f"{major + 1}.0.0"
        return base_version


def get_dynamic_dependencies(
    pyproject_path: str = "pyproject.toml",
    use_exact_match: bool = False,
    use_compatible_release: bool = False,
) -> List[str]:
    """
    Read dependencies from pyproject.toml and update internal package versions.

    Internal packages (microsoft-agents-a365-*) can use different versioning strategies:

    1. Minimum version (default, recommended):
       >= base_version
       Example: >= 0.1.0
       - Maximum flexibility for consumers

    2. Compatible release:
       >= base_version, < next_major_version
       Example: >= 0.1.0, < 0.2.0
       - Allows updates within major version

    3. Exact match:
       == current_version
       Example: == 0.1.0.dev5
       - Forces exact version match

    External packages keep their original version constraints.

    Args:
        pyproject_path: Path to the pyproject.toml file (default: "pyproject.toml")
        use_exact_match: If True, use == for internal packages
        use_compatible_release: If True, use >= with < upper bound

    Returns:
        List of dependency strings with updated internal package versions

    Raises:
        FileNotFoundError: If pyproject.toml doesn't exist
        ValueError: If pyproject.toml is invalid or missing required fields
    """
    package_version = get_package_version()

    # Extract base version using robust parsing
    base_version = get_base_version(package_version)

    # Load TOML library (Python 3.11+ has built-in, older versions need tomli)
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # Fallback for older Python
        except ImportError:
            raise ImportError(
                "Failed to import TOML library. For Python < 3.11, please install tomli: "
                "pip install tomli"
            )

    # Read and parse pyproject.toml with comprehensive error handling
    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Could not find {pyproject_path}. "
            f"Ensure the file exists in the expected location. "
            f"Current working directory may be incorrect."
        )
    except PermissionError:
        raise PermissionError(
            f"Permission denied reading {pyproject_path}. Check file permissions."
        )
    except Exception as e:
        # Catch TOML decode errors (attribute may vary by library)
        if "TOML" in type(e).__name__ or "Decode" in type(e).__name__:
            raise ValueError(
                f"Invalid TOML syntax in {pyproject_path}: {e}. "
                f"Please check the file for syntax errors."
            )
        # Re-raise unexpected errors
        raise RuntimeError(f"Unexpected error reading {pyproject_path}: {type(e).__name__}: {e}")

    # Validate pyproject.toml structure
    if "project" not in pyproject:
        raise ValueError(
            f"{pyproject_path} is missing [project] section. "
            f"This is required for PEP 621 compliant packages."
        )

    dependencies = pyproject.get("project", {}).get("dependencies", [])

    # Warn if no dependencies found (might be intentional, so don't fail)
    if not dependencies:
        # Note: Using print instead of logging to avoid additional dependencies
        # In production, consider using logging module
        import sys

        print(
            f"Warning: No dependencies found in {pyproject_path}. "
            f"This may be intentional for packages with no dependencies.",
            file=sys.stderr,
        )

    # Update internal package versions dynamically
    updated_dependencies = []
    for dep in dependencies:
        if not isinstance(dep, str):
            # Skip non-string dependencies (shouldn't happen, but be defensive)
            print(
                f"Warning: Skipping non-string dependency: {dep}",
                file=sys.stderr,
            )
            continue

        if dep.startswith("microsoft-agents-a365-"):
            # Extract package name (everything before >=, ==, or other operators)
            pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0].strip()

            if use_exact_match:
                # Exact match: == current_version
                updated_dependencies.append(f"{pkg_name} == {package_version}")
            elif use_compatible_release:
                # Compatible release: >= base_version, < next_major
                next_major = get_next_major_version(base_version)
                updated_dependencies.append(f"{pkg_name} >= {base_version}, < {next_major}")
            else:
                # Minimum version (default): >= base_version
                updated_dependencies.append(f"{pkg_name} >= {base_version}")
        else:
            # Keep external dependencies as-is
            updated_dependencies.append(dep)

    return updated_dependencies
