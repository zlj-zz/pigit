"""Tests for repo observe config and imperative panel refresh."""

import os
import tempfile
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from pigit.config import Config
from pigit.observe.types import ChangeBatch, ChangeKind, ObserveContext
from pigit.termui.types import LayerKind


class TestObserveConfig:
    """Test parsing of [app] observe configuration."""

    @pytest.mark.parametrize(
        "toml_content,repo_observe,observe_worktree",
        [
            ("", True, True),
            ("[app]\nrepo_observe = false\n", False, True),
            ("[app]\nobserve_worktree = false\n", True, False),
            (
                "[app]\nrepo_observe = false\nobserve_worktree = false\n",
                False,
                False,
            ),
        ],
    )
    def test_repo_observe_flags(self, toml_content, repo_observe, observe_worktree):
        """Config file can set repo_observe and observe_worktree."""
        Config._instances.clear()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            path = f.name
        try:
            cfg = Config(path=path, version="test", auto_load=False)
            cfg.load_config()
            app = cfg.get().app
            assert app.repo_observe is repo_observe
            assert app.observe_worktree is observe_worktree
            assert not hasattr(app, "auto_refresh_interval")
        finally:
            os.unlink(path)
            Config._instances.clear()

    def test_legacy_auto_refresh_interval_warns_and_is_ignored(self):
        """Legacy auto_refresh_interval is ignored with a warning."""
        Config._instances.clear()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[app]\nauto_refresh_interval = 30.0\nrepo_observe = true\n")
            path = f.name
        try:
            cfg = Config(path=path, version="test", auto_load=False)
            cfg.load_config()
            assert not hasattr(cfg.get().app, "auto_refresh_interval")
            assert any("auto_refresh_interval" in w for w in cfg._warnings)
        finally:
            os.unlink(path)
            Config._instances.clear()


@pytest.fixture
def app():
    """Create a PigitApplication with mocked Config."""
    from pigit.app import PigitApplication
    from pigit.config_data import AppConfig

    application = PigitApplication(config=AppConfig())
    application.build_root()
    yield application


@pytest.fixture
def mock_panel(app):
    """Set up mocked tab_view, presented panel, and VM for _refresh_active_panel."""
    mock_tab = MagicMock()
    app._tab_view = mock_tab
    with patch("pigit.app.resolve_presentation_leaf") as mock_resolve:
        panel = MagicMock(spec=["refresh", "_vm"])
        # Force Component-like path: use a real type without overridden refresh
        from pigit.termui.component import Component

        class _Panel(Component):
            pass

        real = _Panel()
        real._vm = MagicMock()
        mock_resolve.return_value = real
        yield real


class TestRefreshActivePanel:
    """Test _refresh_active_panel overlay skip and VM refresh."""

    def test_skips_when_modal_open(self, app, mock_panel):
        """_refresh_active_panel skips when a MODAL is open."""
        stack = MagicMock()
        stack.top.side_effect = lambda kind: (
            object() if kind == LayerKind.MODAL else None
        )
        app._root = MagicMock()
        app._root._layer_stack = stack
        app._refresh_active_panel()
        mock_panel._vm.refresh.assert_not_called()

    def test_refreshes_vm_when_no_overlay(self, app, mock_panel):
        """_refresh_active_panel calls active VM refresh when no MODAL/SHEET."""
        stack = MagicMock()
        stack.top.return_value = None
        app._root = MagicMock()
        app._root._layer_stack = stack
        app._refresh_active_panel()
        mock_panel._vm.refresh.assert_called_once()

    def test_toast_does_not_block_refresh(self, app, mock_panel):
        """TOAST alone must not skip imperative refresh."""
        stack = MagicMock()

        def top(kind):
            return object() if kind == LayerKind.TOAST else None

        stack.top.side_effect = top
        app._root = MagicMock()
        app._root._layer_stack = stack
        app._refresh_active_panel()
        mock_panel._vm.refresh.assert_called_once()

    def test_skips_when_no_vm(self, app):
        """_refresh_active_panel skips when active panel has no _vm."""
        stack = MagicMock()
        stack.top.return_value = None
        app._root = MagicMock()
        app._root._layer_stack = stack
        mock_tab = MagicMock()
        app._tab_view = mock_tab
        with patch("pigit.app.resolve_presentation_leaf") as mock_resolve:
            from pigit.termui.component import Component

            class _Panel(Component):
                pass

            panel = _Panel()
            mock_resolve.return_value = panel
            app._refresh_active_panel()


class TestObserveBatchSinks:
    """Test ChangeBatch routing to header and panels."""

    def test_head_batch_schedules_header_and_branch_refresh(self, app):
        from pigit.app_branch import BranchPanel

        schedule = MagicMock()
        refresh = MagicMock()
        app._observe_host._deps = replace(
            app._observe_host._deps,
            schedule_reload_header=schedule,
            refresh_list_panel=refresh,
        )
        panel = object.__new__(BranchPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=panel):
            app._on_observe_batch(
                ChangeBatch(kinds=frozenset({ChangeKind.HEAD}), paths=frozenset())
            )

        schedule.assert_called_once()
        refresh.assert_called_once_with(panel)

    def test_worktree_meta_refreshes_status_when_active(self, app):
        """WORKTREE_META on Status tab triggers list refresh and dirty dot
        update (not the full header reload)."""
        from pigit.app_status import StatusPanel

        schedule = MagicMock()
        dirty = MagicMock()
        refresh = MagicMock()
        app._observe_host._deps = replace(
            app._observe_host._deps,
            schedule_reload_header=schedule,
            refresh_header_dirty=dirty,
            refresh_list_panel=refresh,
        )
        panel = object.__new__(StatusPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=panel):
            app._on_observe_batch(
                ChangeBatch(
                    kinds=frozenset({ChangeKind.WORKTREE_META}),
                    paths=frozenset({"foo.py"}),
                )
            )

        # Worktree changes refresh the Status panel (the tab's Status sibling),
        # not the presentation leaf object as such.
        refresh.assert_called_once_with(app._status_panel)
        # Pure worktree edits only move the dirty dot; branch tracking does
        # not need a two-subprocess reload per batch.
        dirty.assert_called_once()
        schedule.assert_not_called()

    def test_head_refreshes_header_but_not_status_list(self, app):
        """HEAD on Status tab triggers header reload only (list stays)."""
        from pigit.app_status import StatusPanel

        schedule = MagicMock()
        refresh = MagicMock()
        app._observe_host._deps = replace(
            app._observe_host._deps,
            schedule_reload_header=schedule,
            refresh_list_panel=refresh,
        )
        panel = object.__new__(StatusPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=panel):
            app._on_observe_batch(
                ChangeBatch(
                    kinds=frozenset({ChangeKind.HEAD}),
                    paths=frozenset({"HEAD"}),
                )
            )

        schedule.assert_called_once()
        refresh.assert_not_called()

    def test_build_observe_roots_attaches_worktree_only_for_status(self, app):
        """Worktree root is present only while Status is the active panel."""
        from pigit.app_status import StatusPanel
        from pigit.app_branch import BranchPanel

        app._observe_host._observe_ctx = ObserveContext(
            repo_root="/repo",
            git_dir="/repo/.git",
            common_dir="/repo/.git",
        )
        app._config.observe_worktree = True
        app._status_vm.items.set([])

        status = object.__new__(StatusPanel)
        branch = object.__new__(BranchPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=status):
            roots = app._build_observe_roots()
        assert any(r.kind == "worktree" for r in roots)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=branch):
            roots = app._build_observe_roots()
        assert all(r.kind != "worktree" for r in roots)
        # Digest is only trustworthy while a worktree root is actually watched;
        # on other tabs it must read None so the header falls back to a direct
        # probe instead of a stale dirty flag.
        assert app._observe_host.worktree_dirty is None

    def test_worktree_dirty_stale_on_non_status_tab(self, app):
        """worktree_dirty returns None when Status is not the active tab."""
        from pigit.app_status import StatusPanel
        from pigit.app_branch import BranchPanel

        app._observe_host._observe_ctx = ObserveContext(
            repo_root="/repo",
            git_dir="/repo/.git",
            common_dir="/repo/.git",
        )
        app._config.observe_worktree = True
        app._status_vm.items.set([])
        status = object.__new__(StatusPanel)
        branch = object.__new__(BranchPanel)

        # Status focused: digest recorded and readable.
        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=status):
            app._build_observe_roots()
        app._observe_host._last_worktree_dirty = True
        assert app._observe_host.worktree_dirty is True

        # Switch away: stale digest must not leak into the header probe.
        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=branch):
            app._build_observe_roots()
        assert app._observe_host.worktree_dirty is None

    def test_build_observe_roots_uses_rename_destination_path(self, app):
        """Rename porcelain must not become a WatchRoot path with '->'."""
        from pigit.app_status import StatusPanel
        from pigit.git.model import File

        app._observe_host._observe_ctx = ObserveContext(
            repo_root="/repo",
            git_dir="/repo/.git",
            common_dir="/repo/.git",
        )
        app._config.observe_worktree = True
        renamed = File(
            name="src/renamed.txt",
            display_str="src/orig.txt -> src/renamed.txt",
            short_status="R ",
            has_staged_change=True,
            has_unstaged_change=False,
            tracked=True,
            deleted=False,
            added=False,
            has_merged_conflicts=False,
            has_inline_merged_conflicts=False,
        )
        app._status_vm.items.set([renamed])
        status = object.__new__(StatusPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=status):
            roots = app._build_observe_roots()
        file_roots = [r.path for r in roots if r.kind == "file"]
        assert any(p.endswith("src/renamed.txt") for p in file_roots)
        assert all("->" not in p for p in file_roots)

    def test_preview_file_batch_reloads_status_preview(self, app):
        """PREVIEW_FILE on Status with large-screen preview calls reload()."""
        from pigit.app_status import StatusPanel

        app._tab_view = MagicMock()
        app._schedule_reload_header = MagicMock()
        app._refresh_list_panel = MagicMock()
        app._diff_preview_wanted = True
        app._is_large_screen = True
        app._preview_panel = MagicMock()
        panel = object.__new__(StatusPanel)

        with patch("pigit.app_observe.resolve_presentation_leaf", return_value=panel):
            app._on_observe_batch(
                ChangeBatch(
                    kinds=frozenset({ChangeKind.PREVIEW_FILE}),
                    paths=frozenset({"foo.py"}),
                )
            )

        app._preview_panel.reload.assert_called_once()
        app._refresh_list_panel.assert_not_called()
