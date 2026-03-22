"""Tests for build configuration and Docker hardening.

Red-green TDD: These tests fail on main (missing .dockerignore, unpinned deps,
root user in Dockerfile) and pass on feat/ci-docker-hardening.
"""

import os
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


class TestDockerignore:
    """Tests for .dockerignore — fails on main because the file doesn't exist."""

    def test_dockerignore_exists(self):
        """A .dockerignore file must exist to keep build context small."""
        assert (PROJECT_ROOT / ".dockerignore").exists(), \
            ".dockerignore is missing — .git and caches are included in the Docker build context"

    def test_dockerignore_excludes_git(self):
        """.git directory should be excluded from Docker build context."""
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert ".git" in content

    def test_dockerignore_excludes_pycache(self):
        """__pycache__ should be excluded from Docker build context."""
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert "__pycache__" in content

    def test_dockerignore_excludes_data(self):
        """data/ should be excluded (it's a volume mount, not baked in)."""
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert "data/" in content


class TestRequirements:
    """Tests for pinned dependency versions — fails on main because deps are unpinned."""

    def test_requirements_has_version_constraints(self):
        """All dependencies must have version constraints for reproducibility."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
        for line in lines:
            assert re.search(r'[~=<>!]', line), \
                f"Dependency '{line}' has no version constraint — builds are not reproducible"

    def test_requirements_includes_pytest_cov(self):
        """pytest-cov must be included for coverage reporting in CI."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "pytest-cov" in content, "pytest-cov is missing — CI coverage reporting won't work"

    def test_requirements_includes_linter(self):
        """A linting tool (ruff) must be included for CI quality checks."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "ruff" in content, "ruff is missing — CI linting step won't work"


class TestDockerfile:
    """Tests for Dockerfile security hardening — fails on main because it runs as root."""

    def test_dockerfile_has_non_root_user(self):
        """Dockerfile must create and switch to a non-root user."""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "useradd" in content or "adduser" in content, \
            "Dockerfile doesn't create a non-root user — containers run as root"
        assert "USER" in content, \
            "Dockerfile doesn't switch to non-root user with USER directive"

    def test_dockerfile_user_is_not_root(self):
        """The USER directive must not be 'root'."""
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        user_lines = [l for l in content.splitlines() if l.strip().startswith("USER")]
        assert len(user_lines) > 0, "No USER directive found"
        for line in user_lines:
            assert "root" not in line.lower(), "USER directive should not be root"


CI_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT_PATH = PROJECT_ROOT / ".github" / "dependabot.yml"


@pytest.mark.skipif(not CI_PATH.exists(), reason=".github excluded from Docker image by .dockerignore")
class TestCIWorkflow:
    """Tests for CI workflow improvements — fails on main because lint/coverage steps are missing."""

    def test_ci_workflow_has_lint_step(self):
        """CI must include a linting step."""
        content = CI_PATH.read_text()
        assert "ruff" in content or "flake8" in content or "lint" in content.lower(), \
            "CI workflow has no linting step"

    def test_ci_workflow_has_coverage(self):
        """CI must include coverage reporting."""
        content = CI_PATH.read_text()
        assert "--cov" in content, "CI workflow doesn't include coverage reporting (--cov flag)"


@pytest.mark.skipif(not DEPENDABOT_PATH.exists(), reason=".github excluded from Docker image by .dockerignore")
class TestDependabotConfig:
    """Tests for Dependabot configuration."""

    def test_dependabot_file_exists(self):
        """Dependabot must be enabled with a repository config file."""
        assert DEPENDABOT_PATH.exists(), ".github/dependabot.yml is missing"

    def test_dependabot_declares_supported_ecosystems(self):
        """Dependabot should monitor the repo's Python, Docker, and Actions dependencies."""
        content = DEPENDABOT_PATH.read_text()
        assert 'package-ecosystem: "pip"' in content
        assert 'package-ecosystem: "docker"' in content
        assert 'package-ecosystem: "github-actions"' in content

    def test_dependabot_uses_root_directory(self):
        """All dependency manifests live from the repository root/default workflow path."""
        content = DEPENDABOT_PATH.read_text()
        assert content.count('directory: "/"') == 3
