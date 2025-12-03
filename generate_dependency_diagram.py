# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Script to generate a dependency diagram for Microsoft Agent 365 SDK packages.
Reads pyproject.toml files and creates a Mermaid diagram showing internal package dependencies.
"""

import re
import tomllib
from pathlib import Path
from typing import Dict, List, Set


class PackageInfo:
    """Information about a package and its dependencies."""

    def __init__(self, name: str, package_type: str, path: Path):
        self.name = name
        self.package_type = package_type
        self.path = path
        self.dependencies: Set[str] = set()


def read_pyproject_toml(path: Path) -> Dict:
    """Read and parse a pyproject.toml file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def extract_dependencies(pyproject_data: Dict, package_names: Set[str]) -> Set[str]:
    """Extract internal package dependencies from pyproject.toml data."""
    dependencies = set()

    if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
        for dep in pyproject_data["project"]["dependencies"]:
            # Extract package name (before any version specifier)
            # Use regex to handle multiple version specifiers (e.g., "package>=1.0,<2.0")
            dep_name = re.split(r"[><=!~]", dep)[0].strip()

            # Only include if it's one of our internal packages
            if dep_name in package_names:
                dependencies.add(dep_name)

    return dependencies


def generate_mermaid_diagram(packages: List[PackageInfo]) -> str:
    """Generate a Mermaid diagram from package information."""

    # Color scheme based on package types
    colors = {
        "Notifications": {"fill": "#ffcdd2", "stroke": "#c62828", "color": "#280505"},  # Red
        "Runtime": {"fill": "#bbdefb", "stroke": "#1565c0", "color": "#0d1a26"},  # Blue
        "Observability": {"fill": "#c8e6c9", "stroke": "#2e7d32", "color": "#142a14"},  # Green
        "Observability Extensions": {
            "fill": "#e8f5e9",
            "stroke": "#66bb6a",
            "color": "#1f3d1f",
        },  # Light Green
        "Tooling": {"fill": "#ffe0b2", "stroke": "#e65100", "color": "#331a00"},  # Orange
        "Tooling Extensions": {
            "fill": "#fff3e0",
            "stroke": "#fb8c00",
            "color": "#4d2600",
        },  # Light Orange
    }

    lines = ["```mermaid", "graph LR"]
    lines.append("    %% Package Nodes")

    # Create node definitions with shortened names for display
    node_map = {}
    for pkg in packages:
        # Create a short identifier for the node
        node_id = pkg.name.replace("-", "_")
        node_map[pkg.name] = node_id

        # Create display name (remove microsoft-agents-a365- prefix for cleaner display)
        display_name = pkg.name
        lines.append(f'    {node_id}["{display_name}"]')

    lines.append("")
    lines.append("    %% Dependencies")

    # Add dependency edges
    for pkg in packages:
        if pkg.dependencies:
            source_id = node_map[pkg.name]
            for dep_name in sorted(pkg.dependencies):
                if dep_name in node_map:
                    target_id = node_map[dep_name]
                    lines.append(f"    {source_id} --> {target_id}")

    lines.append("")
    lines.append("    %% Styling")

    # Group packages by type for styling
    packages_by_type: Dict[str, List[str]] = {}
    for pkg in packages:
        if pkg.package_type not in packages_by_type:
            packages_by_type[pkg.package_type] = []
        packages_by_type[pkg.package_type].append(node_map[pkg.name])

    # Apply styles
    for pkg_type, color_spec in colors.items():
        if pkg_type in packages_by_type:
            class_name = pkg_type.lower().replace(" ", "_")
            lines.append(
                f"    classDef {class_name} fill:{color_spec['fill']},stroke:{color_spec['stroke']},color:{color_spec['color']},stroke-width:2px"
            )
            node_list = ",".join(packages_by_type[pkg_type])
            lines.append(f"    class {node_list} {class_name}")

    lines.append("```")

    return "\n".join(lines)


def determine_package_type(package_name: str) -> str:
    """Determine the package type based on package name."""
    if "notifications" in package_name:
        return "Notifications"
    elif "runtime" in package_name:
        return "Runtime"
    elif "observability-extensions" in package_name:
        return "Observability Extensions"
    elif "observability" in package_name:
        return "Observability"
    elif "tooling-extensions" in package_name:
        return "Tooling Extensions"
    elif "tooling" in package_name:
        return "Tooling"
    else:
        return "Other"


def main():
    """Main function to generate the dependency diagram."""

    # Get repository root
    repo_root = Path(__file__).parent

    # Read workspace members from root pyproject.toml
    root_pyproject_path = repo_root / "pyproject.toml"
    if not root_pyproject_path.exists():
        print(f"Error: {root_pyproject_path} not found")
        return

    root_pyproject = read_pyproject_toml(root_pyproject_path)

    # Extract workspace members
    workspace_members = []
    if "tool" in root_pyproject and "uv" in root_pyproject["tool"]:
        if "workspace" in root_pyproject["tool"]["uv"]:
            workspace_members = root_pyproject["tool"]["uv"]["workspace"].get("members", [])

    if not workspace_members:
        print("Error: No workspace members found in pyproject.toml")
        return

    print(f"Found {len(workspace_members)} workspace members")

    # Build package configs from workspace members
    package_configs = []
    for member_path in workspace_members:
        # Determine package type from path
        pkg_type = determine_package_type(member_path)
        package_configs.append((member_path, pkg_type))

    # Collect all package names first and cache pyproject data
    all_package_names = set()
    packages: List[PackageInfo] = []
    pyproject_data_cache: Dict[str, Dict] = {}

    for path_str, pkg_type in package_configs:
        pyproject_path = repo_root / path_str / "pyproject.toml"

        if not pyproject_path.exists():
            print(f"Warning: {pyproject_path} not found")
            continue

        pyproject_data = read_pyproject_toml(pyproject_path)
        if "project" not in pyproject_data or "name" not in pyproject_data["project"]:
            print(f"Warning: {pyproject_path} is missing project.name field")
            continue
        pkg_name = pyproject_data["project"]["name"]
        all_package_names.add(pkg_name)

        # Cache the pyproject data to avoid reading the file again
        pyproject_data_cache[pkg_name] = pyproject_data

        pkg_info = PackageInfo(pkg_name, pkg_type, pyproject_path)
        packages.append(pkg_info)

    # Extract dependencies for each package using cached data
    for pkg in packages:
        pyproject_data = pyproject_data_cache[pkg.name]
        pkg.dependencies = extract_dependencies(pyproject_data, all_package_names)

    # Generate Mermaid diagram
    diagram = generate_mermaid_diagram(packages)

    # Write to markdown file
    output_path = repo_root / "DEPENDENCIES.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Microsoft Agent 365 SDK Python Package Dependencies\n\n")
        f.write(
            "This diagram shows the internal dependencies between Microsoft Agent 365 SDK Python packages.\n\n"
        )
        f.write(diagram)
        f.write("\n\n")
        f.write("## Package Types\n\n")
        f.write("- **Notifications** (Red): Notification and messaging extensions\n")
        f.write("- **Runtime** (Blue): Core runtime components\n")
        f.write("- **Observability** (Green): Telemetry and monitoring core\n")
        f.write(
            "- **Observability Extensions** (Light Green): Framework-specific observability integrations\n"
        )
        f.write("- **Tooling** (Orange): Agent tooling SDK core\n")
        f.write(
            "- **Tooling Extensions** (Light Orange): Framework-specific tooling integrations\n"
        )

    print(f"Dependency diagram generated successfully: {output_path}")

    # Print summary
    print(f"\nAnalyzed {len(packages)} packages:")
    for pkg in sorted(packages, key=lambda p: p.name):
        if pkg.dependencies:
            deps = ", ".join(sorted(dep for dep in pkg.dependencies))
            print(f"  {pkg.name} → {deps}")
        else:
            print(f"  {pkg.name} (no internal dependencies)")


if __name__ == "__main__":
    main()
