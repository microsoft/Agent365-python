# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom build backend that wraps setuptools.build_meta to inject centralized
version constraints into published wheel metadata.

Note: Individual sdist publishing is not supported; packages are published as
wheels only from CI.

Usage in package pyproject.toml:
  [build-system]
  requires = ["setuptools>=68", "wheel", "tzdata", "tomlkit", "packaging"]
  build-backend = "build_backend"

The build backend module is resolved via PYTHONPATH, which must include the
path to this directory (versioning/helper) when building. The CI pipeline sets
this automatically. For local builds, use 'uv build' from the repo root, or
set PYTHONPATH manually:
  export PYTHONPATH="$(git rev-parse --show-toplevel)/versioning/helper:$PYTHONPATH"
  python -m build --no-isolation --wheel
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import tomlkit
from setup_utils import _parse_root_constraints
from setuptools.build_meta import (
    build_editable,
    build_sdist,
    build_wheel,
    get_requires_for_build_editable,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
    prepare_metadata_for_build_editable,
    prepare_metadata_for_build_wheel,
)

__all__ = [
    "build_editable",
    "build_sdist",
    "build_wheel",
    "get_requires_for_build_editable",
    "get_requires_for_build_sdist",
    "get_requires_for_build_wheel",
    "prepare_metadata_for_build_editable",
    "prepare_metadata_for_build_wheel",
]


def _get_package_version() -> str:
    """Get the package version from the environment variable set by CI/CD."""
    return os.environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")


def _apply_constraints_to_list(
    deps: tomlkit.items.Array,
    root_constraints: dict[str, str],
    package_version: str,
) -> bool:
    """
    Apply version constraints to a tomlkit dependency array in-place.

    Returns True if any changes were made.
    """
    from packaging.requirements import Requirement

    changed = False
    for i, dep in enumerate(deps):
        if not isinstance(dep, str):
            continue
        stripped = dep.strip()

        # Parse the requirement to correctly handle environment markers
        # e.g. 'pkg; python_version < "3.12"' should not be treated as constrained
        try:
            req = Requirement(stripped)
            name = req.name
            has_specifier = bool(req.specifier)
            marker_suffix = f" ; {req.marker}" if req.marker else ""
        except Exception:
            # Fallback: split off markers manually
            base, sep, marker_rest = stripped.partition(";")
            name = base.strip()
            has_specifier = False
            marker_suffix = f";{marker_rest}" if sep else ""

        # Skip deps that already have version constraints
        if has_specifier:
            continue

        if name.startswith("microsoft-agents-a365-"):
            # Pin internal deps to exact build version
            deps[i] = f"{name} == {package_version}{marker_suffix}"
            changed = True
        else:
            # Apply root constraint for external deps
            normalized = name.lower().replace("_", "-")
            if normalized in root_constraints:
                deps[i] = f"{root_constraints[normalized]}{marker_suffix}"
                changed = True
            else:
                print(
                    f"Warning: No constraint found for bare dependency '{name}'. "
                    f"It will be published without a version constraint.",
                    file=sys.stderr,
                )
    return changed


def _apply_constraints(pyproject_path: Path) -> str | None:
    """
    Rewrite pyproject.toml to include version constraints on all bare deps.

    Uses tomlkit for safe TOML round-tripping that preserves comments,
    formatting, and handles multiline arrays and alternate quoting styles.

    - Internal deps (microsoft-agents-a365-*) get pinned to == current build version
    - External deps get the centralized constraint from root pyproject.toml
    - Both [project].dependencies and [project.optional-dependencies] are processed

    Returns the original content so it can be restored, or None if no changes needed.
    """
    original = pyproject_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(original)

    project = doc.get("project")
    if project is None:
        return None

    root_constraints = _parse_root_constraints(pyproject_path)
    package_version = _get_package_version()

    changed = False

    # Process [project].dependencies
    deps = project.get("dependencies")
    if deps is not None:
        changed |= _apply_constraints_to_list(deps, root_constraints, package_version)

    # Process [project.optional-dependencies]
    opt_deps = project.get("optional-dependencies")
    if opt_deps is not None:
        for group_name in opt_deps:
            group = opt_deps[group_name]
            changed |= _apply_constraints_to_list(group, root_constraints, package_version)

    if not changed:
        return None

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return original


def _restore(pyproject_path: Path, original: str | None) -> None:
    """Restore the original pyproject.toml content."""
    if original is not None:
        pyproject_path.write_text(original, encoding="utf-8")


# Override build_wheel to inject constraints
_orig_build_wheel = build_wheel


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    pyproject = Path("pyproject.toml")
    original = _apply_constraints(pyproject)
    try:
        return _orig_build_wheel(wheel_directory, config_settings, metadata_directory)
    finally:
        _restore(pyproject, original)


# Override build_sdist to inject constraints
_orig_build_sdist = build_sdist


def build_sdist(sdist_directory, config_settings=None):
    pyproject = Path("pyproject.toml")
    original = _apply_constraints(pyproject)
    try:
        return _orig_build_sdist(sdist_directory, config_settings)
    finally:
        _restore(pyproject, original)


# Override prepare_metadata_for_build_wheel to inject constraints
_orig_prepare_metadata = prepare_metadata_for_build_wheel


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    pyproject = Path("pyproject.toml")
    original = _apply_constraints(pyproject)
    try:
        return _orig_prepare_metadata(metadata_directory, config_settings)
    finally:
        _restore(pyproject, original)
