# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Shared utilities for setup.py files across all Microsoft Agent 365 Python SDK packages.

This module provides helper functions to dynamically set internal package versions
at build time, ensuring all packages in the monorepo use the exact same version.
"""

import re
from os import environ
from pathlib import Path


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


def _find_root_pyproject(start_path: Path | None = None) -> Path | None:
    """
    Walk up from start_path to find the monorepo root pyproject.toml.

    The root is identified by having [tool.uv.workspace] or a
    constraint-dependencies key under [tool.uv].

    Args:
        start_path: A path to start walking up from (e.g. a package's pyproject.toml).
                    If None, starts from the current working directory.

    Returns:
        Path to the root pyproject.toml, or None if not found.
    """
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None

    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path).resolve()

    # If start_path is a file, begin from its parent directory
    if start_path.is_file():
        start_path = start_path.parent

    for parent in [start_path] + list(start_path.parents):
        candidate = parent / "pyproject.toml"
        if not candidate.exists():
            continue
        try:
            with open(candidate, "rb") as f:
                data = tomllib.load(f)
            uv_cfg = data.get("tool", {}).get("uv", {})
            if "workspace" in uv_cfg or "constraint-dependencies" in uv_cfg:
                return candidate
        except Exception:
            continue
    return None


def _parse_root_constraints(start_path: Path | None = None) -> dict[str, str]:
    """
    Parse constraint-dependencies from the monorepo root pyproject.toml.

    Walks up from start_path to find the root, then parses constraints.

    Args:
        start_path: A path to start walking up from (e.g. a package's pyproject.toml).
                    If None, starts from the current working directory.

    Returns:
        A dict mapping normalized package names to their full constraint strings.
        Example: {"semantic-kernel": "semantic-kernel >= 1.39.3"}
    """
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return {}

    root_pyproject_path = _find_root_pyproject(start_path)
    if root_pyproject_path is None:
        return {}

    try:
        with open(root_pyproject_path, "rb") as f:
            root_data = tomllib.load(f)
    except (FileNotFoundError, PermissionError):
        return {}

    from packaging.requirements import Requirement

    constraints_list = root_data.get("tool", {}).get("uv", {}).get("constraint-dependencies", [])
    constraints: dict[str, str] = {}
    for entry in constraints_list:
        if not isinstance(entry, str):
            continue
        try:
            req = Requirement(entry)
            normalized = req.name.lower().replace("_", "-")
        except Exception:
            # Fallback for entries that packaging can't parse
            pkg_name = re.split(r"\s*[<>=!~]", entry, maxsplit=1)[0].strip()
            normalized = pkg_name.lower().replace("_", "-")
        constraints[normalized] = entry
    return constraints


def _has_version_constraint(dep: str) -> bool:
    """Check if a dependency string already includes a version constraint.

    Uses packaging.requirements.Requirement for robust parsing that correctly
    ignores environment markers (e.g. ``; python_version < '3.12'``).
    """
    from packaging.requirements import Requirement

    try:
        req = Requirement(dep)
        return bool(req.specifier)
    except Exception:
        # If packaging can't parse it, fall back to simple heuristic
        # on the portion before any marker.
        base = dep.split(";", 1)[0].strip()
        return bool(re.search(r"[<>=!~]", base))


def get_dynamic_dependencies(
    pyproject_path: str = "pyproject.toml",
    use_exact_match: bool = False,
    use_compatible_release: bool = False,
) -> list[str]:
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

    External packages without version constraints get the centralized constraint
    from the root pyproject.toml constraint-dependencies, ensuring published packages
    enforce minimum versions for security and compatibility.

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
            ) from None

    # Read and parse pyproject.toml with comprehensive error handling
    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"Could not find {pyproject_path}. "
            f"Ensure the file exists in the expected location. "
            f"Current working directory may be incorrect."
        ) from err
    except PermissionError as err:
        raise PermissionError(
            f"Permission denied reading {pyproject_path}. Check file permissions."
        ) from err
    except Exception as e:
        # Catch TOML decode errors (attribute may vary by library)
        if "TOML" in type(e).__name__ or "Decode" in type(e).__name__:
            raise ValueError(
                f"Invalid TOML syntax in {pyproject_path}: {e}. "
                f"Please check the file for syntax errors."
            ) from e
        # Re-raise unexpected errors
        raise RuntimeError(
            f"Unexpected error reading {pyproject_path}: {type(e).__name__}: {e}"
        ) from e

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

    # Load centralized constraints from root pyproject.toml so that published
    # packages enforce the same minimum versions used during development.
    # Uses walk-up approach to find the root, independent of directory depth.
    root_constraints = _parse_root_constraints(Path(pyproject_path).resolve())

    from packaging.requirements import Requirement

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

        # Parse with packaging.requirements.Requirement for robust handling
        # of version specifiers, extras, and environment markers.
        try:
            req = Requirement(dep)
            pkg_name = req.name
            has_specifier = bool(req.specifier)
            marker_suffix = f" ; {req.marker}" if req.marker else ""
        except Exception:
            # Fallback for unparseable entries
            pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0].split(";")[0].strip()
            has_specifier = _has_version_constraint(dep)
            base_part, sep, marker_rest = dep.partition(";")
            marker_suffix = f";{marker_rest}" if sep else ""

        if pkg_name.startswith("microsoft-agents-a365-"):
            if use_exact_match:
                updated_dependencies.append(f"{pkg_name} == {package_version}{marker_suffix}")
            elif use_compatible_release:
                next_major = get_next_major_version(base_version)
                updated_dependencies.append(
                    f"{pkg_name} >= {base_version}, < {next_major}{marker_suffix}"
                )
            else:
                updated_dependencies.append(f"{pkg_name} >= {base_version}{marker_suffix}")
        elif not has_specifier:
            # External dep with no version constraint — apply root constraint if available
            normalized = pkg_name.lower().replace("_", "-")
            if normalized in root_constraints:
                updated_dependencies.append(f"{root_constraints[normalized]}{marker_suffix}")
            else:
                updated_dependencies.append(dep)
        else:
            # External dependency already has a version constraint — keep as-is
            updated_dependencies.append(dep)

    return updated_dependencies
