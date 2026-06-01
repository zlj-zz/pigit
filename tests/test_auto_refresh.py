"""Tests for auto-refresh configuration and overlay skip logic."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from pigit.config import Config


class TestAutoRefreshConfig:
    """Test parsing of [tui] configuration section."""

    @pytest.mark.parametrize(
        "toml_content,expected",
        [
            ("", 10.0),  # default when no [tui] section
            ('[tui]\nauto_refresh_interval = 30.0\n', 30.0),
            ('[tui]\nauto_refresh_interval = 0\n', 0.0),
        ],
    )
    def test_auto_refresh_interval(self, toml_content, expected):
        """Config file can set, override, or disable auto_refresh_interval."""
        Config._instances.clear()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            path = f.name
        try:
            cfg = Config(path=path, version="test", auto_load=False)
            cfg.load_config()
            assert cfg.get().tui.auto_refresh_interval == expected
        finally:
            os.unlink(path)
            Config._instances.clear()


@pytest.fixture
def app():
    """Create a PigitApplication with mocked Config."""
    from pigit.app import PigitApplication
    from pigit.config_data import ConfigData

    with patch("pigit.app.Config") as mock_cfg_cls:
        mock_cfg_cls.return_value.get.return_value = ConfigData()
        yield PigitApplication()


@pytest.fixture
def mock_panel(app):
    """Set up mocked tab_view, presented panel, and VM for _refresh_active_panel."""
    with patch("pigit.app.by_id") as mock_by_id:
        mock_tab = MagicMock()
        mock_by_id.return_value = mock_tab
        with patch("pigit.app.resolve_presented") as mock_resolve:
            panel = MagicMock()
            panel._vm = MagicMock()
            mock_resolve.return_value = panel
            yield panel


class TestRefreshActivePanel:
    """Test _refresh_active_panel overlay skip logic."""

    def test_skips_when_overlay_open(self, app, mock_panel):
        """_refresh_active_panel skips when an overlay is open."""
        app._root = MagicMock()
        app._root.has_overlay_open.return_value = True
        app._refresh_active_panel()
        mock_panel._vm.refresh.assert_not_called()

    def test_refreshes_vm_when_no_overlay(self, app, mock_panel):
        """_refresh_active_panel calls vm.refresh when no overlay is open."""
        app._root = MagicMock()
        app._root.has_overlay_open.return_value = False
        app._refresh_active_panel()
        mock_panel._vm.refresh.assert_called_once()

    def test_skips_when_no_vm(self, app):
        """_refresh_active_panel skips when active panel has no _vm."""
        app._root = MagicMock()
        app._root.has_overlay_open.return_value = False
        with patch("pigit.app.by_id") as mock_by_id:
            mock_tab = MagicMock()
            mock_by_id.return_value = mock_tab
            with patch("pigit.app.resolve_presented") as mock_resolve:
                panel = MagicMock()
                del panel._vm
                mock_resolve.return_value = panel
                app._refresh_active_panel()
