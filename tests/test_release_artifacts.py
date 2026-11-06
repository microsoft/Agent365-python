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
    ("problem", "expected_error"),
    [
        ("none", None),
        ("sentinel", None),
        ("retired", "Unexpected or duplicate distribution"),
        ("dependency", "depends on retired distribution"),
        ("stale-version", "Stale version in"),
        ("missing", "Missing distributions"),
        ("extra-file", "Unexpected release artifact"),
        ("payload", "Retired observability payload"),
        ("duplicate", "Unexpected or duplicate distribution"),
        ("filename-name", "Filename and metadata disagree"),
        ("filename-version", "Filename and metadata disagree"),
        ("corrupt-zip", "File is not a zip file"),
    ],
)
def test_release_gate(release_dir: Path, problem: str, expected_error: str | None) -> None:
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
        next(release_dir.glob("microsoft_agents_a365_runtime-*.whl")).unlink()
        _wheel(release_dir, runtime, version="1.2.2")
    elif problem == "missing":
        next(release_dir.glob("*.whl")).unlink()
    elif problem == "extra-file":
        (release_dir / "old.tar.gz").write_bytes(b"stale sdist")
    elif problem == "payload":
        with ZipFile(next(release_dir.glob("*.whl")), "a") as archive:
            archive.writestr("microsoft_agents_a365/observability/core/__init__.py", "")
    elif problem == "duplicate":
        path = _wheel(release_dir, runtime)
        path.with_name(path.name.replace("-py3-", "-py2-")).write_bytes(path.read_bytes())
    elif problem == "filename-name":
        _wheel(release_dir, runtime).rename(release_dir / "not_runtime-1.2.3-py3-none-any.whl")
    elif problem == "filename-version":
        path = _wheel(release_dir, runtime)
        path.rename(path.with_name(path.name.replace("1.2.3", "1.2.4")))
    elif problem == "corrupt-zip":
        _wheel(release_dir, runtime).write_bytes(b"not a zip archive")
    elif problem == "sentinel":
        (release_dir / ".gitignore").write_text("*\n")

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
    if expected_error is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "Release artifact verification failed" in result.stderr
        assert expected_error in result.stderr
        if problem == "stale-version":
            assert "expected 1.2.3" in result.stderr
