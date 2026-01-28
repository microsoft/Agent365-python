# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Tests for validating dependency version constraints across all packages.

This test ensures that upper bound version constraints (e.g., < 0.6.0) on dependencies
do not become incompatible with the latest published versions of those packages.

Background: We encountered an issue where microsoft-agents-a365-tooling had a constraint
`microsoft-agents-hosting-core >= 0.4.0, < 0.6.0` but the samples used 0.7.0, causing
the package resolver to silently pick older versions instead of the latest.
"""

import re
import tomllib
from pathlib import Path

import pytest

# Packages in this repo that should be checked for version constraint issues
INTERNAL_PACKAGES = {
    "microsoft-agents-a365-tooling",
    "microsoft-agents-a365-tooling-extensions-openai",
    "microsoft-agents-a365-tooling-extensions-agentframework",
    "microsoft-agents-a365-tooling-extensions-semantickernel",
    "microsoft-agents-a365-tooling-extensions-azureaifoundry",
    "microsoft-agents-a365-observability-core",
    "microsoft-agents-a365-observability-extensions-openai",
    "microsoft-agents-a365-observability-extensions-agent-framework",
    "microsoft-agents-a365-observability-extensions-semantickernel",
    "microsoft-agents-a365-runtime",
    "microsoft-agents-a365-notifications",
}

# Known external packages where we should be careful about upper bounds
EXTERNAL_PACKAGES_TO_CHECK = {
    "microsoft-agents-hosting-core",
    "microsoft-agents-hosting-aiohttp",
    "microsoft-agents-authentication-msal",
    "microsoft-agents-activity",
}


def get_repo_root() -> Path:
    """Get the root directory of the Agent365-python repository."""
    current = Path(__file__).resolve()
    # Navigate up to find the repo root (contains 'libraries' folder)
    for parent in current.parents:
        if (parent / "libraries").is_dir():
            return parent
    raise RuntimeError("Could not find repository root")


def find_all_pyproject_files() -> list[Path]:
    """Find all pyproject.toml files in the libraries directory."""
    repo_root = get_repo_root()
    libraries_dir = repo_root / "libraries"
    return list(libraries_dir.glob("**/pyproject.toml"))


def parse_version_constraint(constraint: str) -> dict:
    """
    Parse a version constraint string and extract bounds.

    Examples:
        ">= 0.4.0, < 0.6.0" -> {"lower": "0.4.0", "upper": "0.6.0", "upper_inclusive": False}
        ">= 0.4.0" -> {"lower": "0.4.0", "upper": None}

    Note: Supports version numbers with any number of parts (e.g., "1.0", "1.0.0", "1.0.0.0").
    """
    result = {"lower": None, "upper": None, "upper_inclusive": False, "raw": constraint}

    # Match upper bound patterns: < X.Y or <= X.Y.Z (any dotted numeric version)
    upper_match = re.search(r"(<\s*=?)\s*(\d+(?:\.\d+)*)", constraint)
    if upper_match:
        result["upper"] = upper_match.group(2)
        result["upper_inclusive"] = upper_match.group(1).replace(" ", "") == "<="

    # Match lower bound patterns: >= X.Y or > X.Y.Z (any dotted numeric version)
    lower_match = re.search(r">=?\s*(\d+(?:\.\d+)*)", constraint)
    if lower_match:
        result["lower"] = lower_match.group(1)

    return result


def version_tuple(version: str) -> tuple:
    """Convert version string to tuple for comparison."""
    # Handle pre-release versions like "0.2.1.dev2"
    base_version = version.split(".dev")[0].split("a")[0].split("b")[0].split("rc")[0]
    parts = base_version.split(".")
    return tuple(int(p) for p in parts)


def is_version_compatible(version: str, upper_bound: str, inclusive: bool = False) -> bool:
    """Check if a version is compatible with an upper bound constraint."""
    version_t = version_tuple(version)
    upper_t = version_tuple(upper_bound)

    if inclusive:
        return version_t <= upper_t
    return version_t < upper_t


def get_dependencies_with_upper_bounds(pyproject_path: Path) -> list[dict]:
    """
    Extract dependencies that have upper bound constraints.

    Returns a list of dicts with:
        - package: package name
        - constraint: parsed constraint info
        - file: path to pyproject.toml
    """
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    dependencies = data.get("project", {}).get("dependencies", [])
    results = []

    for dep in dependencies:
        # Parse dependency string: "package-name >= 1.0.0, < 2.0.0"
        match = re.match(r"^([\w\-]+)\s*(.*)$", dep.strip())
        if not match:
            continue

        package_name = match.group(1)
        constraint_str = match.group(2).strip()

        if not constraint_str:
            continue

        constraint = parse_version_constraint(constraint_str)

        if constraint["upper"]:
            results.append({
                "package": package_name,
                "constraint": constraint,
                "file": pyproject_path,
            })

    return results


class TestDependencyConstraints:
    """Tests for dependency version constraints."""

    def test_no_restrictive_upper_bounds_on_external_packages(self):
        """
        Ensure we don't have overly restrictive upper bounds on external packages.

        Upper bounds like `< 0.6.0` can cause issues when the external package
        releases a newer version (e.g., 0.7.0) that our samples depend on.
        This causes the resolver to silently pick older versions of our packages.
        """
        pyproject_files = find_all_pyproject_files()
        issues = []

        for pyproject_path in pyproject_files:
            deps_with_upper = get_dependencies_with_upper_bounds(pyproject_path)

            for dep in deps_with_upper:
                package = dep["package"]

                # Check if this is an external package we should monitor
                if package in EXTERNAL_PACKAGES_TO_CHECK:
                    constraint = dep["constraint"]
                    relative_path = pyproject_path.relative_to(get_repo_root())

                    issues.append(
                        f"  - {relative_path}: '{package}' has upper bound constraint "
                        f"'{constraint['raw']}'. This may cause resolver issues when "
                        f"newer versions are released."
                    )

        if issues:
            pytest.fail(
                "Found dependencies with upper bound constraints that may cause issues:\n"
                + "\n".join(issues)
                + "\n\nConsider removing upper bounds or using a more permissive constraint. "
                "Upper bounds on external packages can cause our packages to be downgraded "
                "when newer versions of the external package are released."
            )

    def test_internal_package_constraints_are_flexible(self):
        """
        Ensure internal packages don't have restrictive upper bounds on each other.

        We want internal packages to be able to evolve together without
        version constraint conflicts.
        """
        pyproject_files = find_all_pyproject_files()
        issues = []

        for pyproject_path in pyproject_files:
            deps_with_upper = get_dependencies_with_upper_bounds(pyproject_path)

            for dep in deps_with_upper:
                package = dep["package"]

                # Check if this is an internal package
                if package in INTERNAL_PACKAGES:
                    constraint = dep["constraint"]
                    relative_path = pyproject_path.relative_to(get_repo_root())

                    issues.append(
                        f"  - {relative_path}: '{package}' has upper bound constraint "
                        f"'{constraint['raw']}'. Internal packages should not have "
                        "upper bounds on each other."
                    )

        if issues:
            pytest.fail(
                "Found internal packages with upper bound constraints:\n"
                + "\n".join(issues)
                + "\n\nInternal packages should use '>= X.Y.Z' without upper bounds "
                "to allow them to evolve together."
            )

    def test_parse_version_constraint(self):
        """Test the version constraint parser."""
        # Test with upper and lower bounds
        result = parse_version_constraint(">= 0.4.0, < 0.6.0")
        assert result["lower"] == "0.4.0"
        assert result["upper"] == "0.6.0"
        assert result["upper_inclusive"] is False

        # Test with only lower bound
        result = parse_version_constraint(">= 1.0.0")
        assert result["lower"] == "1.0.0"
        assert result["upper"] is None

        # Test with inclusive upper bound
        result = parse_version_constraint(">= 2.0.0, <= 3.0.0")
        assert result["lower"] == "2.0.0"
        assert result["upper"] == "3.0.0"
        assert result["upper_inclusive"] is True

    def test_version_compatibility_check(self):
        """Test version compatibility checking."""
        # 0.7.0 is NOT compatible with < 0.6.0
        assert is_version_compatible("0.7.0", "0.6.0", inclusive=False) is False

        # 0.5.9 IS compatible with < 0.6.0
        assert is_version_compatible("0.5.9", "0.6.0", inclusive=False) is True

        # 0.6.0 IS compatible with <= 0.6.0
        assert is_version_compatible("0.6.0", "0.6.0", inclusive=True) is True

        # 0.6.0 is NOT compatible with < 0.6.0
        assert is_version_compatible("0.6.0", "0.6.0", inclusive=False) is False
