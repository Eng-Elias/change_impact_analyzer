"""Comprehensive tests for HookManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.git.hooks import _CIA_MARKER, HookManager

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Create a fake repo directory with .git/hooks."""
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def manager(fake_repo: Path) -> HookManager:
    return HookManager(fake_repo)


# ==================================================================
# Install
# ==================================================================


class TestInstall:
    def test_install_creates_hook(self, manager: HookManager) -> None:
        path = manager.install()
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert _CIA_MARKER in content

    def test_install_default_threshold_none(self, manager: HookManager) -> None:
        manager.install()
        content = manager.hook_path.read_text(encoding="utf-8")
        assert 'BLOCK_THRESHOLD = "none"' in content

    def test_install_high_threshold(self, manager: HookManager) -> None:
        manager.install(block_threshold="high")
        content = manager.hook_path.read_text(encoding="utf-8")
        assert 'BLOCK_THRESHOLD = "high"' in content

    def test_install_medium_threshold(self, manager: HookManager) -> None:
        manager.install(block_threshold="medium")
        content = manager.hook_path.read_text(encoding="utf-8")
        assert 'BLOCK_THRESHOLD = "medium"' in content

    def test_install_low_threshold(self, manager: HookManager) -> None:
        manager.install(block_threshold="low")
        content = manager.hook_path.read_text(encoding="utf-8")
        assert 'BLOCK_THRESHOLD = "low"' in content

    def test_install_missing_hooks_dir(self, tmp_path: Path) -> None:
        mgr = HookManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            mgr.install()

    def test_install_overwrites_existing(self, manager: HookManager) -> None:
        manager.install(block_threshold="none")
        manager.install(block_threshold="high")
        content = manager.hook_path.read_text(encoding="utf-8")
        assert 'BLOCK_THRESHOLD = "high"' in content

    def test_install_returns_path(self, manager: HookManager) -> None:
        path = manager.install()
        assert path == manager.hook_path


# ==================================================================
# Uninstall
# ==================================================================


class TestUninstall:
    def test_uninstall_removes_hook(self, manager: HookManager) -> None:
        manager.install()
        assert manager.uninstall() is True
        assert not manager.hook_path.exists()

    def test_uninstall_no_hook(self, manager: HookManager) -> None:
        assert manager.uninstall() is False

    def test_uninstall_non_cia_hook(self, manager: HookManager) -> None:
        manager.hook_path.write_text("#!/bin/sh\necho other hook\n", encoding="utf-8")
        assert manager.uninstall() is False
        assert manager.hook_path.exists()

    def test_uninstall_after_install(self, manager: HookManager) -> None:
        manager.install()
        assert manager.is_installed() is True
        manager.uninstall()
        assert manager.is_installed() is False


# ==================================================================
# is_installed
# ==================================================================


class TestIsInstalled:
    def test_installed_after_install(self, manager: HookManager) -> None:
        manager.install()
        assert manager.is_installed() is True

    def test_not_installed_initially(self, manager: HookManager) -> None:
        assert manager.is_installed() is False

    def test_not_installed_non_cia_hook(self, manager: HookManager) -> None:
        manager.hook_path.write_text("#!/bin/sh\necho non-cia\n", encoding="utf-8")
        assert manager.is_installed() is False


# ==================================================================
# hook_path property
# ==================================================================


class TestHookPath:
    def test_hook_path(self, manager: HookManager, fake_repo: Path) -> None:
        expected = fake_repo / ".git" / "hooks" / "pre-commit"
        assert manager.hook_path == expected


# ==================================================================
# Analysis helpers
# ==================================================================


class TestAnalysisHelpers:
    def test_generate_report_basic(self) -> None:
        analysis = {"risk_level": "medium", "details": ["Changed utils.py", "3 dependents"]}
        report = HookManager.generate_pre_commit_report(analysis)
        assert "medium" in report
        assert "Changed utils.py" in report
        assert "3 dependents" in report

    def test_generate_report_empty(self) -> None:
        report = HookManager.generate_pre_commit_report({})
        assert "unknown" in report

    def test_generate_report_no_details(self) -> None:
        report = HookManager.generate_pre_commit_report({"risk_level": "low"})
        assert "low" in report
