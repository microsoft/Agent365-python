# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Tests for the custom build backend and setup_utils constraint injection.

Validates that:
- _apply_constraints rewrites bare dependencies with version constraints
- _apply_constraints processes [project.optional-dependencies] as well
- Restoration correctly brings back original content
- Dependencies with existing constraints are left unchanged
- Internal deps get pinned to the build version
- External deps get the centralized root constraint
- Bare external deps with no root constraint emit a warning
- _find_root_pyproject walks up the directory tree correctly
- _parse_root_constraints parses constraint-dependencies from root
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Add versioning/helper to sys.path so we can import setup_utils and build_backend
_helper_dir = str(Path(__file__).resolve().parent.parent / "versioning" / "helper")
if _helper_dir not in sys.path:
    sys.path.insert(0, _helper_dir)

from setup_utils import _find_root_pyproject, _parse_root_constraints  # noqa: E402


class TestFindRootPyproject:
    """Tests for _find_root_pyproject walk-up logic."""

    def test_finds_root_from_library_dir(self, tmp_path: Path) -> None:
        """Walking up from a nested library dir should find the root."""
        # Create root pyproject.toml with workspace marker
        root_toml = tmp_path / "pyproject.toml"
        root_toml.write_text(
            textwrap.dedent("""\
                [tool.uv.workspace]
                members = ["libraries/pkg-a"]

                [tool.uv]
                constraint-dependencies = ["pydantic >= 2.0.0"]
            """),
            encoding="utf-8",
        )

        # Create nested library directory
        lib_dir = tmp_path / "libraries" / "pkg-a"
        lib_dir.mkdir(parents=True)
        pkg_toml = lib_dir / "pyproject.toml"
        pkg_toml.write_text("[project]\nname = 'pkg-a'\n", encoding="utf-8")

        result = _find_root_pyproject(pkg_toml)
        assert result is not None
        assert result == root_toml

    def test_returns_none_when_no_root(self, tmp_path: Path) -> None:
        """Returns None when no root pyproject.toml with workspace marker exists."""
        child_dir = tmp_path / "some" / "nested" / "dir"
        child_dir.mkdir(parents=True)
        # Create a pyproject.toml without workspace markers
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'no-workspace'\n",
            encoding="utf-8",
        )

        result = _find_root_pyproject(child_dir)
        assert result is None

    def test_works_from_file_path(self, tmp_path: Path) -> None:
        """Works when given a file path instead of a directory."""
        root_toml = tmp_path / "pyproject.toml"
        root_toml.write_text(
            '[tool.uv]\nconstraint-dependencies = ["httpx >= 0.27.0"]\n',
            encoding="utf-8",
        )

        sub = tmp_path / "sub"
        sub.mkdir()
        some_file = sub / "pyproject.toml"
        some_file.write_text("[project]\nname = 'sub'\n", encoding="utf-8")

        result = _find_root_pyproject(some_file)
        assert result is not None
        assert result == root_toml


class TestParseRootConstraints:
    """Tests for _parse_root_constraints."""

    def test_parses_constraints(self, tmp_path: Path) -> None:
        """Correctly parses constraint-dependencies from root."""
        root_toml = tmp_path / "pyproject.toml"
        root_toml.write_text(
            textwrap.dedent("""\
                [tool.uv.workspace]
                members = ["libraries/*"]

                [tool.uv]
                constraint-dependencies = [
                    "pydantic >= 2.0.0",
                    "opentelemetry-api >= 1.36.0",
                    "typing-extensions >= 4.0.0",
                ]
            """),
            encoding="utf-8",
        )

        lib_dir = tmp_path / "libraries" / "pkg"
        lib_dir.mkdir(parents=True)

        constraints = _parse_root_constraints(lib_dir)
        assert constraints["pydantic"] == "pydantic >= 2.0.0"
        assert constraints["opentelemetry-api"] == "opentelemetry-api >= 1.36.0"
        assert constraints["typing-extensions"] == "typing-extensions >= 4.0.0"

    def test_normalizes_package_names(self, tmp_path: Path) -> None:
        """Underscores in package names are normalized to hyphens."""
        root_toml = tmp_path / "pyproject.toml"
        root_toml.write_text(
            textwrap.dedent("""\
                [tool.uv]
                workspace = {}
                constraint-dependencies = [
                    "some_package >= 1.0.0",
                ]
            """),
            encoding="utf-8",
        )

        constraints = _parse_root_constraints(tmp_path)
        assert "some-package" in constraints

    def test_returns_empty_when_no_root(self, tmp_path: Path) -> None:
        """Returns empty dict when root not found."""
        isolated_dir = tmp_path / "nowhere"
        isolated_dir.mkdir()
        constraints = _parse_root_constraints(isolated_dir)
        assert constraints == {}


import tomlkit  # noqa: E402
from setup_utils import _has_version_constraint, get_dynamic_dependencies  # noqa: E402


class TestApplyConstraints:
    """Tests for build_backend._apply_constraints."""

    @pytest.fixture(autouse=True)
    def _setup_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a minimal monorepo root and package for each test."""
        self.root_dir = tmp_path / "repo"
        self.root_dir.mkdir()

        # Root pyproject.toml with constraint-dependencies
        root_toml = self.root_dir / "pyproject.toml"
        root_toml.write_text(
            textwrap.dedent("""\
                [tool.uv.workspace]
                members = ["libraries/*"]

                [tool.uv]
                constraint-dependencies = [
                    "pydantic >= 2.0.0",
                    "opentelemetry-api >= 1.36.0",
                    "typing-extensions >= 4.0.0",
                    "aiohttp >= 3.8.0",
                ]
            """),
            encoding="utf-8",
        )

        # Package directory
        self.pkg_dir = self.root_dir / "libraries" / "pkg-a"
        self.pkg_dir.mkdir(parents=True)

        # Set AGENT365_PYTHON_SDK_PACKAGE_VERSION for internal dep pinning
        monkeypatch.setenv("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "1.2.3")

        # Import build_backend (needs to be done after sys.path setup)
        import build_backend

        self.build_backend = build_backend

    def _write_pkg_toml(self, content: str) -> Path:
        """Write a pyproject.toml in the package dir and return its path."""
        pkg_toml = self.pkg_dir / "pyproject.toml"
        pkg_toml.write_text(textwrap.dedent(content), encoding="utf-8")
        return pkg_toml

    def test_applies_constraints_to_bare_external_deps(self) -> None:
        """Bare external deps get the root constraint."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "pydantic",
                "typing-extensions",
            ]
        """)

        original = self.build_backend._apply_constraints(pkg_toml)
        assert original is not None  # Changes were made

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        deps = list(doc["project"]["dependencies"])
        assert "pydantic >= 2.0.0" in deps
        assert "typing-extensions >= 4.0.0" in deps

    def test_pins_internal_deps_to_build_version(self) -> None:
        """Internal microsoft-agents-a365-* deps get pinned to == build version."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "microsoft-agents-a365-runtime",
                "pydantic",
            ]
        """)

        self.build_backend._apply_constraints(pkg_toml)

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        deps = list(doc["project"]["dependencies"])
        assert "microsoft-agents-a365-runtime == 1.2.3" in deps
        assert "pydantic >= 2.0.0" in deps

    def test_skips_deps_with_existing_constraints(self) -> None:
        """Deps that already have version constraints are left unchanged."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "pydantic >= 1.0.0",
                "typing-extensions",
            ]
        """)

        self.build_backend._apply_constraints(pkg_toml)

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        deps = list(doc["project"]["dependencies"])
        # pydantic should keep its original constraint, not be overridden
        assert "pydantic >= 1.0.0" in deps
        assert "typing-extensions >= 4.0.0" in deps

    def test_returns_none_when_no_changes_needed(self) -> None:
        """Returns None when all deps already have constraints."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "pydantic >= 2.0.0",
            ]
        """)

        result = self.build_backend._apply_constraints(pkg_toml)
        assert result is None

    def test_restore_brings_back_original(self) -> None:
        """_restore correctly restores the original content."""
        content = textwrap.dedent("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "pydantic",
            ]
        """)
        pkg_toml = self._write_pkg_toml(content)

        original = self.build_backend._apply_constraints(pkg_toml)
        assert original is not None

        # File should now have constraints
        modified = pkg_toml.read_text(encoding="utf-8")
        assert "pydantic >= 2.0.0" in modified

        # Restore
        self.build_backend._restore(pkg_toml, original)
        restored = pkg_toml.read_text(encoding="utf-8")
        assert restored == content

    def test_processes_optional_dependencies(self) -> None:
        """Also applies constraints to [project.optional-dependencies] groups."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "pydantic",
            ]

            [project.optional-dependencies]
            azure = [
                "aiohttp",
            ]
        """)

        self.build_backend._apply_constraints(pkg_toml)

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        azure_deps = list(doc["project"]["optional-dependencies"]["azure"])
        assert "aiohttp >= 3.8.0" in azure_deps

    def test_warns_on_bare_dep_with_no_constraint(self, capsys: pytest.CaptureFixture) -> None:
        """Emits a warning for bare deps that have no matching root constraint."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                "unknown-package",
            ]
        """)

        self.build_backend._apply_constraints(pkg_toml)

        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "unknown-package" in captured.err

    def test_preserves_comments_and_formatting(self) -> None:
        """tomlkit preserves comments and formatting in the TOML file."""
        content = textwrap.dedent("""\
            # Package configuration
            [project]
            name = "pkg-a"
            # Runtime dependencies
            dependencies = [
                "pydantic",  # Data validation
                "typing-extensions",
            ]
        """)
        pkg_toml = self.pkg_dir / "pyproject.toml"
        pkg_toml.write_text(content, encoding="utf-8")

        self.build_backend._apply_constraints(pkg_toml)

        modified = pkg_toml.read_text(encoding="utf-8")
        # Comments should be preserved
        assert "# Package configuration" in modified
        assert "# Runtime dependencies" in modified

    def test_handles_no_project_section(self) -> None:
        """Returns None if there is no [project] section."""
        pkg_toml = self._write_pkg_toml("""\
            [build-system]
            requires = ["setuptools"]
        """)

        result = self.build_backend._apply_constraints(pkg_toml)
        assert result is None

    def test_handles_no_dependencies(self) -> None:
        """Returns None if [project] has no dependencies."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
        """)

        result = self.build_backend._apply_constraints(pkg_toml)
        assert result is None

    def test_preserves_environment_markers(self) -> None:
        """Deps with environment markers but no version spec get constraints applied."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                'aiohttp ; python_version < "3.13"',
            ]
        """)

        self.build_backend._apply_constraints(pkg_toml)

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        deps = list(doc["project"]["dependencies"])
        # Should get the root constraint AND preserve the marker
        assert len(deps) == 1
        assert "aiohttp >= 3.8.0" in deps[0]
        assert "python_version" in deps[0]

    def test_marker_only_dep_not_treated_as_constrained(self) -> None:
        """A dep with only a marker (no version spec) should not be skipped."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = [
                'pydantic ; sys_platform == "linux"',
            ]
        """)

        original = self.build_backend._apply_constraints(pkg_toml)
        # Should be treated as bare dep and get root constraint applied
        assert original is not None

        doc = tomlkit.parse(pkg_toml.read_text(encoding="utf-8"))
        deps = list(doc["project"]["dependencies"])
        assert "pydantic >= 2.0.0" in deps[0]


class TestHasVersionConstraint:
    """Tests for _has_version_constraint with packaging.requirements.Requirement."""

    def test_bare_dep(self) -> None:
        assert _has_version_constraint("pydantic") is False

    def test_dep_with_specifier(self) -> None:
        assert _has_version_constraint("pydantic >= 2.0.0") is True

    def test_dep_with_exact(self) -> None:
        assert _has_version_constraint("pydantic == 2.1.0") is True

    def test_dep_with_compatible(self) -> None:
        assert _has_version_constraint("pydantic ~= 2.0") is True

    def test_dep_with_marker_only(self) -> None:
        """Marker-only deps should NOT be treated as version-constrained."""
        assert _has_version_constraint('pydantic ; python_version < "3.12"') is False

    def test_dep_with_marker_and_specifier(self) -> None:
        """Deps with both specifier and marker should be constrained."""
        assert _has_version_constraint('pydantic >= 2.0 ; python_version >= "3.9"') is True

    def test_dep_with_extras(self) -> None:
        """Extras alone don't count as a version constraint."""
        assert _has_version_constraint("httpx[http2]") is False

    def test_dep_with_extras_and_specifier(self) -> None:
        assert _has_version_constraint("httpx[http2] >= 0.27.0") is True


class TestGetDynamicDependencies:
    """Tests for get_dynamic_dependencies with robust Requirement parsing."""

    @pytest.fixture(autouse=True)
    def _setup_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create a minimal monorepo root for get_dynamic_dependencies tests."""
        self.root_dir = tmp_path / "repo"
        self.root_dir.mkdir()

        root_toml = self.root_dir / "pyproject.toml"
        root_toml.write_text(
            textwrap.dedent("""\
                [tool.uv.workspace]
                members = ["libraries/*"]

                [tool.uv]
                constraint-dependencies = [
                    "pydantic >= 2.0.0",
                    "aiohttp >= 3.8.0",
                ]
            """),
            encoding="utf-8",
        )

        self.pkg_dir = self.root_dir / "libraries" / "pkg-a"
        self.pkg_dir.mkdir(parents=True)

        monkeypatch.setenv("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "1.2.3")

    def _write_pkg_toml(self, deps_toml: str) -> Path:
        """Write a package pyproject.toml and return its path."""
        pkg_toml = self.pkg_dir / "pyproject.toml"
        pkg_toml.write_text(textwrap.dedent(deps_toml), encoding="utf-8")
        return pkg_toml

    def test_external_bare_dep_gets_constraint(self) -> None:
        """Bare external deps get root constraint applied."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = ["pydantic"]
        """)
        result = get_dynamic_dependencies(pyproject_path=str(pkg_toml))
        assert result == ["pydantic >= 2.0.0"]

    def test_external_dep_with_marker_preserves_marker(self) -> None:
        """External dep with marker gets constraint + marker preserved."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = ['pydantic ; python_version >= "3.9"']
        """)
        result = get_dynamic_dependencies(pyproject_path=str(pkg_toml))
        assert len(result) == 1
        assert "pydantic >= 2.0.0" in result[0]
        assert "python_version" in result[0]

    def test_external_dep_no_root_constraint_kept_as_is(self) -> None:
        """External dep with no matching root constraint stays unchanged."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = ["unknown-package"]
        """)
        result = get_dynamic_dependencies(pyproject_path=str(pkg_toml))
        assert result == ["unknown-package"]

    def test_internal_dep_gets_pinned(self) -> None:
        """Internal microsoft-agents-a365-* deps get pinned to build version."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = ["microsoft-agents-a365-runtime"]
        """)
        result = get_dynamic_dependencies(pyproject_path=str(pkg_toml))
        assert result == ["microsoft-agents-a365-runtime >= 1.2.3"]

    def test_internal_dep_with_marker(self) -> None:
        """Internal dep with marker gets pinned and marker preserved."""
        pkg_toml = self._write_pkg_toml("""\
            [project]
            name = "pkg-a"
            dependencies = ['microsoft-agents-a365-runtime ; sys_platform == "linux"']
        """)
        result = get_dynamic_dependencies(pyproject_path=str(pkg_toml))
        assert len(result) == 1
        assert "microsoft-agents-a365-runtime >= 1.2.3" in result[0]
        assert "sys_platform" in result[0]
