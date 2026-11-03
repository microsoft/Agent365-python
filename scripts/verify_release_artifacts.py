# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fail closed unless a wheel-only release contains exactly the active workspace packages."""

import argparse
import sys
import tomllib
from email.parser import BytesParser
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
RETIRED_PREFIX = "microsoft-agents-a365-observability"


def verify_release_artifacts(directory: Path, version: str) -> None:
    """Reject missing, duplicate, unexpected, stale, or observability-bearing wheels."""
    with (ROOT / "pyproject.toml").open("rb") as file:
        members = tomllib.load(file)["tool"]["uv"]["workspace"]["members"]
    expected: set[str] = set()
    for member in members:
        with (ROOT / member / "pyproject.toml").open("rb") as file:
            name = canonicalize_name(tomllib.load(file)["project"]["name"])
        if name.startswith(RETIRED_PREFIX):
            raise ValueError(f"Retired distribution in workspace: {name}")
        expected.add(name)

    seen: set[str] = set()
    for path in sorted(directory.iterdir()):
        # uv creates this sentinel in its output directory.
        if path.name == ".gitignore" and path.is_file():
            continue
        if path.suffix != ".whl" or not path.is_file():
            raise ValueError(f"Unexpected release artifact: {path.name}")
        filename_name, filename_version, _, _ = parse_wheel_filename(path.name)
        with ZipFile(path) as archive:
            entries = archive.namelist()
            if any("microsoft_agents_a365/observability/" in entry for entry in entries):
                raise ValueError(f"Retired observability payload in {path.name}")
            metadata_files = [entry for entry in entries if entry.endswith(".dist-info/METADATA")]
            if len(metadata_files) != 1:
                raise ValueError(f"Expected exactly one METADATA in {path.name}")
            metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        name = canonicalize_name(metadata.get("Name", ""))
        if name not in expected or name in seen:
            raise ValueError(f"Unexpected or duplicate distribution: {name}")
        if filename_name != name or filename_version != Version(metadata.get("Version", "")):
            raise ValueError(f"Filename and metadata disagree: {path.name}")
        if filename_version != Version(version):
            raise ValueError(f"Stale version in {path.name}; expected {version}")
        for value in metadata.get_all("Requires-Dist", []):
            requirement = Requirement(value)
            if canonicalize_name(requirement.name).startswith(RETIRED_PREFIX):
                raise ValueError(f"{name} depends on retired distribution: {requirement}")
        seen.add(name)
    if seen != expected:
        raise ValueError(f"Missing distributions: {', '.join(sorted(expected - seen))}")
    print(f"Verified {len(seen)} active wheels at version {version}; no retired distributions.")


def main() -> int:
    """Verify a fresh build directory before copying or uploading any release artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        verify_release_artifacts(args.directory, args.version)
    except (OSError, ValueError, BadZipFile, InvalidRequirement) as error:
        print(f"Release artifact verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
