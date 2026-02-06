# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Verify centralized version constraints are properly configured.

This script ensures:
1. No external dependencies in package pyproject.toml files have version constraints
2. All external dependencies have constraints defined in root pyproject.toml
3. No internal dependencies in package pyproject.toml files have version constraints
4. All internal dependencies are listed in root pyproject.toml [tool.uv.sources]

Usage:
    python scripts/verify_constraints.py

Exit codes:
    0 - All checks pass
    1 - Verification failed (version constraints found in packages or missing in root)
"""

import re
import sys
from pathlib import Path

# Pattern to match version constraints like >= 1.0.0, < 2.0, == 1.2.3, ~= 1.0, etc.
VERSION_CONSTRAINT_PATTERN = re.compile(r'^\s*"([^"]+?)(\s*[<>=!~]+\s*[\d][^"]*)"')

# Pattern to extract package name from dependency line (handles with and without version)
# Package names must start with a letter, followed by letters, digits, underscores, dots, or dashes
PACKAGE_NAME_PATTERN = re.compile(r'^\s*"([a-zA-Z][a-zA-Z0-9_.\-]*)')

# Pattern to detect dependency array declarations in pyproject.toml
# Matches: dependencies = [, dev = [, test = [, azure = [, jaeger = [, etc.
# Requires the line to start with the section name (after optional whitespace)
DEPENDENCY_SECTION_PATTERN = re.compile(r"^(dependencies|dev|test|azure|jaeger)\s*=\s*\[")


def is_internal_package(package_name: str) -> bool:
    """Check if a package is an internal workspace package."""
    # Normalize package name (replace underscores with dashes for comparison)
    normalized = package_name.lower().replace("_", "-")
    return normalized.startswith("microsoft-agents-a365-")


def parse_constraint_dependencies(root_pyproject: Path) -> set[str]:
    """Parse constraint-dependencies from root pyproject.toml and return package names."""
    content = root_pyproject.read_text(encoding="utf-8")
    constraints: set[str] = set()

    in_constraint_section = False
    bracket_count = 0

    for line in content.splitlines():
        stripped = line.strip()

        # Detect start of constraint-dependencies (line must start with the key)
        if stripped.startswith("constraint-dependencies") and "=" in stripped:
            in_constraint_section = True
            bracket_count = stripped.count("[") - stripped.count("]")
            continue

        if in_constraint_section:
            bracket_count += stripped.count("[") - stripped.count("]")

            # Extract package name from constraint line
            match = PACKAGE_NAME_PATTERN.match(stripped)
            if match is not None:
                pkg_name = match.group(1).lower().replace("_", "-")
                constraints.add(pkg_name)

            # End of array
            if bracket_count <= 0:
                break

    return constraints


def parse_uv_sources(root_pyproject: Path) -> set[str]:
    """Parse [tool.uv.sources] from root pyproject.toml and return package names."""
    content = root_pyproject.read_text(encoding="utf-8")
    sources: set[str] = set()

    in_sources_section = False

    for line in content.splitlines():
        stripped = line.strip()

        # Detect start of [tool.uv.sources]
        if stripped == "[tool.uv.sources]":
            in_sources_section = True
            continue

        # Detect end of section (another section header)
        if in_sources_section and stripped.startswith("["):
            break

        if in_sources_section:
            # Extract package name from line like: package-name = { workspace = true }
            # Must have = with { workspace = true } on the right side
            if "=" in stripped:
                parts = stripped.split("=", 1)
                if len(parts) == 2:
                    value_part = parts[1].strip()
                    # Check for workspace declaration pattern (handles spacing variations)
                    if (
                        value_part.startswith("{")
                        and "workspace" in value_part
                        and "true" in value_part
                    ):
                        pkg_name = parts[0].strip().lower().replace("_", "-")
                        sources.add(pkg_name)

    return sources


def check_package_file(
    pyproject_path: Path, root_constraints: set[str], uv_sources: set[str]
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Check a package pyproject.toml for violations.

    Returns:
        Tuple of (
            external_version_violations,
            missing_root_constraints,
            internal_version_violations,
            missing_uv_sources
        )
    """
    content = pyproject_path.read_text(encoding="utf-8")
    external_version_violations: list[str] = []
    missing_constraints: list[str] = []
    internal_version_violations: list[str] = []
    missing_uv_sources: list[str] = []

    # Track which section we're in
    in_dependencies_section = False
    section_name = ""
    bracket_count = 0

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        # Detect dependency sections using precise pattern matching
        # Matches: dependencies = [, dev = [, test = [, azure = [, jaeger = [
        section_match = DEPENDENCY_SECTION_PATTERN.match(stripped)
        if section_match is not None:
            in_dependencies_section = True
            section_name = section_match.group(1)
            bracket_count = stripped.count("[") - stripped.count("]")
            continue

        if in_dependencies_section:
            bracket_count += stripped.count("[") - stripped.count("]")

            # Check for version constraints in dependency lines
            match = VERSION_CONSTRAINT_PATTERN.match(stripped)
            if match is not None:
                pkg_name = match.group(1).strip()
                version_spec = match.group(2).strip()

                if is_internal_package(pkg_name):
                    # Internal packages should have NO version constraints
                    internal_version_violations.append(
                        f"Line {line_num}: {pkg_name}{version_spec} (in {section_name})"
                    )
                else:
                    # External packages should have no version constraints
                    external_version_violations.append(
                        f"Line {line_num}: {pkg_name}{version_spec} (in {section_name})"
                    )

            # Check if package exists in appropriate location
            pkg_match = PACKAGE_NAME_PATTERN.match(stripped)
            if pkg_match is not None:
                pkg_name = pkg_match.group(1).lower().replace("_", "-")

                if is_internal_package(pkg_name):
                    # Internal packages should be in [tool.uv.sources]
                    if pkg_name not in uv_sources:
                        missing_uv_sources.append(
                            f"Line {line_num}: {pkg_name} (in {section_name})"
                        )
                else:
                    # External packages should have root constraints
                    if pkg_name not in root_constraints:
                        missing_constraints.append(
                            f"Line {line_num}: {pkg_name} (in {section_name})"
                        )

            # End of array
            if bracket_count <= 0:
                in_dependencies_section = False

    return (
        external_version_violations,
        missing_constraints,
        internal_version_violations,
        missing_uv_sources,
    )


def main() -> int:
    """Main entry point."""
    # Find root directory (containing pyproject.toml)
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent

    root_pyproject = root_dir / "pyproject.toml"
    if not root_pyproject.exists():
        print(f"ERROR: Root pyproject.toml not found at {root_pyproject}")
        return 1

    libraries_dir = root_dir / "libraries"
    if not libraries_dir.exists():
        print(f"ERROR: Libraries directory not found at {libraries_dir}")
        return 1

    print("Verifying centralized version constraints...")
    print(f"Root: {root_dir}")
    print()

    # Parse root constraints and uv sources
    root_constraints = parse_constraint_dependencies(root_pyproject)
    print(f"Found {len(root_constraints)} constraints in root pyproject.toml")

    uv_sources = parse_uv_sources(root_pyproject)
    print(f"Found {len(uv_sources)} packages in [tool.uv.sources]")
    print()

    # Check all package pyproject.toml files
    all_external_violations: dict[str, list[str]] = {}
    all_missing_constraints: dict[str, list[str]] = {}
    all_internal_violations: dict[str, list[str]] = {}
    all_missing_sources: dict[str, list[str]] = {}
    packages_checked = 0

    for package_dir in sorted(libraries_dir.iterdir()):
        if not package_dir.is_dir():
            continue

        pyproject_path = package_dir / "pyproject.toml"
        if not pyproject_path.exists():
            continue

        packages_checked += 1
        ext_violations, missing, int_violations, missing_src = check_package_file(
            pyproject_path, root_constraints, uv_sources
        )

        if ext_violations:
            all_external_violations[package_dir.name] = ext_violations
        if missing:
            all_missing_constraints[package_dir.name] = missing
        if int_violations:
            all_internal_violations[package_dir.name] = int_violations
        if missing_src:
            all_missing_sources[package_dir.name] = missing_src

    print(f"Checked {packages_checked} packages")
    print()

    # Report results
    has_errors = False

    if all_external_violations:
        has_errors = True
        print("=" * 70)
        print("ERROR: Found version constraints on external dependencies")
        print("       (These should be removed - constraints are centralized in root)")
        print("=" * 70)
        for package, violations in sorted(all_external_violations.items()):
            print(f"\n{package}:")
            for v in violations:
                print(f"  - {v}")
        print()

    if all_internal_violations:
        has_errors = True
        print("=" * 70)
        print("ERROR: Found version constraints on internal dependencies")
        print("       (Internal deps should have NO version constraint, not even >= 0.0.0)")
        print("=" * 70)
        for package, violations in sorted(all_internal_violations.items()):
            print(f"\n{package}:")
            for v in violations:
                print(f"  - {v}")
        print()

    if all_missing_constraints:
        has_errors = True
        print("=" * 70)
        print("ERROR: Found external dependencies without root constraints")
        print("       (These need to be added to root pyproject.toml constraint-dependencies)")
        print("=" * 70)
        for package, missing in sorted(all_missing_constraints.items()):
            print(f"\n{package}:")
            for m in missing:
                print(f"  - {m}")
        print()

    if all_missing_sources:
        has_errors = True
        print("=" * 70)
        print("ERROR: Found internal dependencies not in [tool.uv.sources]")
        print("       (These need to be added to root pyproject.toml [tool.uv.sources])")
        print("=" * 70)
        for package, missing in sorted(all_missing_sources.items()):
            print(f"\n{package}:")
            for m in missing:
                print(f"  - {m}")
        print()

    if has_errors:
        print("FAILED: Verification found issues that need to be fixed.")
        return 1

    print("SUCCESS: All checks passed!")
    print("  - No version constraints found on external dependencies in package files")
    print("  - No version constraints found on internal dependencies in package files")
    print("  - All external dependencies have root constraints")
    print("  - All internal dependencies are in [tool.uv.sources]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
