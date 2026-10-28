# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Release gates must reject stale or retired artifacts, not just skip uploading them."""

import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_workspace_has_no_retired_packages() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        workspace = tomllib.load(file)["tool"]["uv"]
    assert not any("observability" in member for member in workspace["workspace"]["members"])
    assert not any("observability" in name for name in workspace["sources"])


def _wheel(directory: Path, name: str, version: str = "1.2.3", dependency: str = "") -> Path:
    normalized = name.replace("-", "_")
    path = directory / f"{normalized}-{version}-py3-none-any.whl"
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    if dependency:
        metadata += f"Requires-Dist: {dependency}\n"
    with ZipFile(path, "w") as archive:
        archive.writestr(f"{normalized}-{version}.dist-info/METADATA", metadata + "\n")
    return path


@pytest.fixture
def release_dir(tmp_path: Path) -> Path:
    for manifest in (ROOT / "libraries").glob("*/pyproject.toml"):
        with manifest.open("rb") as file:
            name = tomllib.load(file)["project"]["name"]
        if "observability" not in name:
            _wheel(tmp_path, name)
    return tmp_path


@pytest.mark.parametrize(
    "problem",
    ["none", "retired", "dependency", "stale-version", "missing", "extra-file", "payload"],
)
def test_release_gate(release_dir: Path, problem: str) -> None:
    runtime = "microsoft-agents-a365-runtime"
    if problem == "retired":
        _wheel(release_dir, "microsoft-agents-a365-observability-core")
    elif problem == "dependency":
        _wheel(
            release_dir,
            runtime,
            dependency='microsoft_agents_a365_observability_core; extra == "legacy"',
        )
    elif problem == "stale-version":
        _wheel(release_dir, runtime, version="1.2.2")
    elif problem == "missing":
        next(release_dir.glob("*.whl")).unlink()
    elif problem == "extra-file":
        (release_dir / "old.tar.gz").write_bytes(b"stale sdist")
    elif problem == "payload":
        with ZipFile(next(release_dir.glob("*.whl")), "a") as archive:
            archive.writestr("microsoft_agents_a365/observability/core/__init__.py", "")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_release_artifacts.py"),
            str(release_dir),
            "--version",
            "1.2.3",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if problem == "none":
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "Release artifact verification failed" in result.stderr
