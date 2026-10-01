# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Ensure published wheels enforce security floors without the workspace lockfile."""

import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_PREFIX = "microsoft-agents-a365-"
SECURITY_FLOORS = {
    "anyio": "4.14.2",
    "langchain-core": "1.3.3",
    "langsmith": "0.8.18",
    "mcp": "1.28.1",
    "pyasn1": "0.6.4",
    "pyjwt": "2.14.0",
    "python-multipart": "0.0.30",
}
MCP_REQUIREMENTS = {"mcp", "anyio", "python-multipart", "pyjwt"}
EXPECTED_REQUIREMENTS = {
    "notifications": {"pyjwt"},
    "observability-core": {"pyjwt"},
    "observability-extensions-agent-framework": {"pyjwt"},
    "observability-extensions-langchain": {"langchain-core", "langsmith", "anyio", "pyjwt"},
    "observability-extensions-openai": MCP_REQUIREMENTS,
    "observability-extensions-semantic-kernel": MCP_REQUIREMENTS,
    "observability-hosting": {"pyjwt"},
    "runtime": {"pyjwt"},
    "tooling": {"pyjwt"},
    "tooling-extensions-agentframework": MCP_REQUIREMENTS | {"pyasn1"},
    "tooling-extensions-azureaifoundry": {"pyjwt"},
    "tooling-extensions-googleadk": MCP_REQUIREMENTS | {"pyasn1"},
    "tooling-extensions-openai": MCP_REQUIREMENTS,
    "tooling-extensions-semantickernel": MCP_REQUIREMENTS,
}


@pytest.fixture(scope="module")
def published_requirements(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, list[Requirement]]:
    """Build real wheels offline in a copy so backend rewrites cannot affect the checkout."""
    workspace = tmp_path_factory.mktemp("wheels")
    shutil.copy2(REPO_ROOT / "pyproject.toml", workspace / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "LICENSE.md", workspace / "LICENSE.md")
    shutil.copytree(
        REPO_ROOT / "versioning" / "helper",
        workspace / "versioning" / "helper",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    # Short directory names leave room for setuptools build paths on Windows.
    for index, manifest in enumerate(sorted((REPO_ROOT / "libraries").glob("*/pyproject.toml"))):
        shutil.copytree(
            manifest.parent,
            workspace / "libraries" / f"p{index}",
            ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
        )
    wheel_dir = workspace / "wheels"
    wheel_dir.mkdir()
    env = {
        **os.environ,
        "PYTHONPATH": str(workspace / "versioning" / "helper"),
        "AGENT365_PYTHON_SDK_PACKAGE_VERSION": "0.0.0",
    }
    requirements: dict[str, list[Requirement]] = {}
    for pyproject in sorted((workspace / "libraries").glob("*/pyproject.toml")):
        original = pyproject.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import build_backend, sys; build_backend.build_wheel(sys.argv[1])",
                str(wheel_dir),
            ],
            cwd=pyproject.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, (
            f"Wheel build failed for {pyproject.parent.name}:\n{result.stdout}\n{result.stderr}"
        )
        assert pyproject.read_bytes() == original, f"Build did not restore {pyproject}"

    for wheel in sorted(wheel_dir.glob("*.whl")):
        with ZipFile(wheel) as archive:
            metadata_files = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            assert len(metadata_files) == 1, f"Expected one METADATA file in {wheel}"
            metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        name = metadata["Name"]
        assert name is not None
        requirements[canonicalize_name(name)] = [
            Requirement(value) for value in metadata.get_all("Requires-Dist", [])
        ]

    assert set(requirements) == {PACKAGE_PREFIX + suffix for suffix in EXPECTED_REQUIREMENTS}
    return requirements


def _runtime_requirements(
    name: str, published: dict[str, list[Requirement]]
) -> Iterator[Requirement]:
    """Follow internal wheel requirements, never the lockfile or optional development extras."""
    pending = [name]
    visited: set[str] = set()
    while pending:
        package = pending.pop()
        if package in visited:
            continue
        visited.add(package)
        for requirement in published[package]:
            if requirement.marker is not None:
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency.startswith(PACKAGE_PREFIX):
                assert str(requirement.specifier) == "==0.0.0"
                pending.append(dependency)
            else:
                yield requirement


@pytest.mark.parametrize("package_suffix", EXPECTED_REQUIREMENTS)
def test_published_security_floors(
    package_suffix: str, published_requirements: dict[str, list[Requirement]]
) -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as file:
        root = tomllib.load(file)
    constraints = {
        canonicalize_name(requirement.name): requirement
        for value in root["tool"]["uv"]["constraint-dependencies"]
        for requirement in [Requirement(value)]
    }
    requirements = {
        canonicalize_name(requirement.name): requirement
        for requirement in _runtime_requirements(
            PACKAGE_PREFIX + package_suffix, published_requirements
        )
    }
    # Also reject adding unrelated framework dependencies to lightweight packages.
    assert requirements.keys() & SECURITY_FLOORS.keys() == EXPECTED_REQUIREMENTS[package_suffix]
    for name in EXPECTED_REQUIREMENTS[package_suffix]:
        requirement = requirements[name]
        assert requirement.specifier == constraints[name].specifier, (
            f"{package_suffix} does not publish the centralized {name} constraint"
        )
        assert any(
            specifier.operator == ">="
            and Version(specifier.version) >= Version(SECURITY_FLOORS[name])
            for specifier in requirement.specifier
        ), f"{package_suffix} allows vulnerable versions of {name}: {requirement.specifier}"
