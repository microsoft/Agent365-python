# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom build backend that wraps setuptools.build_meta to inject centralized
version constraints into published wheel metadata.

Usage in package pyproject.toml:
  [build-system]
  requires = ["setuptools>=68", "wheel", "tzdata"]
  build-backend = "build_backend"
  backend-path = ["../../versioning/helper"]
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

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


def _load_root_constraints() -> dict[str, str]:
    """Load constraint-dependencies from the monorepo root pyproject.toml."""
    root = Path("pyproject.toml").resolve()
    # Walk up to find the root (contains [tool.uv.workspace])
    for parent in [root.parent] + list(root.parents):
        candidate = parent / "pyproject.toml"
        if not candidate.exists():
            continue
        with open(candidate, "rb") as f:
            data = tomllib.load(f)
        uv_cfg = data.get("tool", {}).get("uv", {})
        if "workspace" in uv_cfg or "constraint-dependencies" in uv_cfg:
            constraints_list = uv_cfg.get("constraint-dependencies", [])
            constraints: dict[str, str] = {}
            for entry in constraints_list:
                if not isinstance(entry, str):
                    continue
                pkg_name = re.split(r"\s*[<>=!~]", entry, maxsplit=1)[0].strip()
                normalized = pkg_name.lower().replace("_", "-")
                constraints[normalized] = entry
            return constraints
    return {}


def _get_package_version() -> str:
    """Get the package version from the environment variable set by CI/CD."""
    return os.environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")


def _apply_constraints(pyproject_path: Path) -> str | None:
    """
    Rewrite pyproject.toml to include version constraints on all bare deps.

    - Internal deps (microsoft-agents-a365-*) get pinned to == current build version
    - External deps get the centralized constraint from root pyproject.toml

    Returns the original content so it can be restored, or None if no changes needed.
    """
    original = pyproject_path.read_text(encoding="utf-8")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    if not deps:
        return None

    root_constraints = _load_root_constraints()
    package_version = _get_package_version()

    modified = original
    changed = False

    for dep in deps:
        if not isinstance(dep, str):
            continue
        stripped = dep.strip()

        # Skip deps that already have version constraints
        if re.search(r"[<>=!~]", stripped):
            continue

        if stripped.startswith("microsoft-agents-a365-"):
            # Pin internal deps to exact build version
            constrained = f"{stripped} == {package_version}"
        else:
            # Apply root constraint for external deps
            normalized = stripped.lower().replace("_", "-")
            if normalized in root_constraints:
                constrained = root_constraints[normalized]
            else:
                continue

        # Replace the bare dep name with the constrained version in the TOML
        pattern = rf'(\s*")({re.escape(dep)})(")'
        replacement = rf"\g<1>{constrained}\g<3>"
        new_modified = re.sub(pattern, replacement, modified)
        if new_modified != modified:
            modified = new_modified
            changed = True

    if not changed:
        return None

    pyproject_path.write_text(modified, encoding="utf-8")
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
