"""Tests for DiffViewer file history mode."""

from unittest.mock import MagicMock, patch

import pytest

from pigit.app_diff import DiffViewer, DiffType

_LOCALGIT_PATH = "pigit.git.local_git.LocalGit"


class TestCurrentFilePath:
    """Extract file path from diff content."""

    def _viewer_with_diff(self, lines: list[str]) -> DiffViewer:
        dv = DiffViewer()
        dv.set_content(lines)
        return dv

    def test_extracts_simple_path(self):
        lines = [
            "diff --git a/src/auth.py b/src/auth.py",
            "--- a/src/auth.py",
            "+++ b/src/auth.py",
            "@@ -0,0 +1,5 @@",
            "+import bcrypt",
        ]
        dv = self._viewer_with_diff(lines)
        dv._i = 4  # cursor on the + line, inside the hunk
        assert dv._current_file_path() == "src/auth.py"

    def test_extracts_path_with_spaces(self):
        lines = [
            'diff --git a/"path with spaces" b/"path with spaces"',
            '--- a/"path with spaces"',
            '+++ b/"path with spaces"',
            "@@ -0,0 +1,2 @@",
            "+hello",
        ]
        dv = self._viewer_with_diff(lines)
        dv._i = 4
        assert dv._current_file_path() == "path with spaces"

    def test_returns_none_when_no_hunk(self):
        dv = DiffViewer()
        dv._i = 0
        assert dv._current_file_path() is None

    def test_returns_none_for_malformed_header(self):
        lines = [
            "not a diff header",
            "some content",
        ]
        dv = self._viewer_with_diff(lines)
        dv._i = 1
        assert dv._current_file_path() is None


class TestFileHistoryState:
    """Enter/exit File History mode preserves and restores diff state."""

    @pytest.fixture
    def viewer(self):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "abc1234"
        dv.come_from = MagicMock()
        dv.set_content([
            "diff --git a/src/main.py b/src/main.py",
            "--- a/src/main.py",
            "+++ b/src/main.py",
            "@@ -1,3 +1,3 @@",
            " old_line",
            "-removed",
            "+added",
        ])
        dv._i = 2
        return dv

    @patch(_LOCALGIT_PATH)
    def test_enter_saves_diff_state(self, mock_git_cls, viewer):
        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [
            ("abc1234", "feat: initial"),
            ("def5678", "feat: update"),
        ]
        mock_git.get_file_at_commit.return_value = "line1\nline2"
        mock_git_cls.return_value = mock_git

        viewer._enter_file_history("src/main.py")

        assert viewer._file_history_mode is True
        assert viewer._file_history_path == "src/main.py"
        assert viewer._saved_diff_state is not None
        assert viewer._saved_diff_state.diff_type == DiffType.COMMIT
        assert viewer._saved_diff_state.scroll_i == 2
        assert viewer._saved_diff_state.come_from is viewer.come_from

    @patch(_LOCALGIT_PATH)
    def test_exit_restores_diff_state(self, mock_git_cls, viewer):
        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [
            ("abc1234", "feat: initial"),
        ]
        mock_git.get_file_at_commit.return_value = "line1"
        mock_git_cls.return_value = mock_git

        original_content = list(viewer._content)
        viewer._enter_file_history("src/main.py")
        assert viewer._content != original_content

        viewer._exit_file_history()

        assert viewer._file_history_mode is False
        assert viewer._content == original_content
        assert viewer._diff_type == DiffType.COMMIT
        assert viewer._i == 2

    @patch(_LOCALGIT_PATH)
    def test_multiple_enter_exit_cycles(self, mock_git_cls, viewer):
        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [("abc1234", "x")]
        mock_git.get_file_at_commit.return_value = "a"
        mock_git_cls.return_value = mock_git

        for _ in range(3):
            viewer._enter_file_history("src/main.py")
            assert viewer._file_history_mode is True
            viewer._exit_file_history()
            assert viewer._file_history_mode is False
            assert viewer._diff_type == DiffType.COMMIT
            assert viewer._i == 2


class TestFileHistoryNavigation:
    """p/n navigation between file history commits."""

    @pytest.fixture
    def viewer_in_history(self):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content([
            "diff --git a/f.py b/f.py",
            "@@ -1,1 +1,1 @@",
            " old",
        ])

        with patch(_LOCALGIT_PATH) as mock_cls:
            mock_git = MagicMock()
            mock_git.get_file_history.return_value = [
                ("sha0", "newest"),
                ("sha1", "middle"),
                ("sha2", "oldest"),
            ]
            mock_git.get_file_at_commit.return_value = "content"
            mock_cls.return_value = mock_git
            dv._enter_file_history("f.py")

        return dv

    def test_p_goes_to_older_commit(self, viewer_in_history):
        dv = viewer_in_history
        assert dv._file_history_index == 0  # starts at newest (sha0)
        dv._prev_file_commit()
        assert dv._file_history_index == 1  # now at sha1 (older)

    def test_n_goes_to_newer_commit(self, viewer_in_history):
        dv = viewer_in_history
        dv._file_history_index = 1
        dv._next_file_commit()
        assert dv._file_history_index == 0  # back to sha0 (newer)

    def test_p_stops_at_oldest(self, viewer_in_history):
        dv = viewer_in_history
        dv._file_history_index = 2  # oldest
        dv._prev_file_commit()
        assert dv._file_history_index == 2  # stays at oldest

    def test_n_stops_at_newest(self, viewer_in_history):
        dv = viewer_in_history
        dv._file_history_index = 0  # newest
        dv._next_file_commit()
        assert dv._file_history_index == 0  # stays at newest

    def test_p_n_noop_outside_history_mode(self):
        dv = DiffViewer()
        dv._file_history_mode = False
        dv._prev_file_commit()
        dv._next_file_commit()
        # Should not raise


class TestToggleFileHistory:
    """v key binding guards."""

    def test_v_shows_toast_for_staged_diff(self):
        dv = DiffViewer()
        dv._diff_type = DiffType.STAGED
        dv.set_content(["diff --git a/f.py b/f.py", "@@ -1,1 +1,1 @@", " x"])
        dv._i = 2

        with patch("pigit.app_diff.show_toast") as mock_toast:
            dv._toggle_file_history()
            mock_toast.assert_called_once()
            assert "only available for commit diffs" in mock_toast.call_args[0][0]

    def test_v_shows_toast_when_no_file(self):
        dv = DiffViewer()
        dv._diff_type = DiffType.COMMIT
        dv.set_content([])

        with patch("pigit.app_diff.show_toast") as mock_toast:
            dv._toggle_file_history()
            mock_toast.assert_called_once()
            assert "No file" in mock_toast.call_args[0][0]


class TestFileHistoryHelp:
    """Help entries reflect current mode."""

    def test_diff_mode_shows_v_for_commit(self):
        dv = DiffViewer()
        dv._diff_type = DiffType.COMMIT
        entries = dv.get_help_entries()
        keys = [k for k, _ in entries]
        assert "v" in keys

    def test_diff_mode_shows_h_for_unstaged(self):
        dv = DiffViewer()
        dv._diff_type = DiffType.UNSTAGED
        entries = dv.get_help_entries()
        keys = [k for k, _ in entries]
        assert "H" in keys
        assert "v" not in keys

    def test_file_history_mode_help(self):
        dv = DiffViewer()
        dv._file_history_mode = True
        entries = dv.get_help_entries()
        keys = [k for k, _ in entries]
        assert "p" in keys
        assert "n" in keys
        assert "d" in keys
        assert "v" not in keys


class TestFileHistoryCache:
    """LRU caching of file content."""

    @patch(_LOCALGIT_PATH)
    def test_cache_hits_avoid_repeated_git_calls(self, mock_git_cls):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content([
            "diff --git a/f.py b/f.py",
            "@@ -1,1 +1,1 @@",
            " x",
        ])

        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [
            ("sha0", "newest"),
            ("sha1", "older"),
        ]
        mock_git.get_file_at_commit.return_value = "cached content"
        mock_git_cls.return_value = mock_git

        dv._enter_file_history("f.py")
        assert mock_git.get_file_at_commit.call_count == 1

        dv._file_history_index = 1
        dv._load_file_history_at_current_index()
        assert mock_git.get_file_at_commit.call_count == 2

        # Navigate back to sha0 — should hit cache
        dv._file_history_index = 0
        dv._load_file_history_at_current_index()
        assert mock_git.get_file_at_commit.call_count == 2  # no extra call


class TestFileHistoryBinaryAndDeleted:
    """Edge cases: binary files and deleted files."""

    @patch(_LOCALGIT_PATH)
    def test_shows_binary_message(self, mock_git_cls):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content([
            "diff --git a/f.bin b/f.bin",
            "@@ -1,1 +1,1 @@",
            " x",
        ])

        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [("sha0", "add binary")]
        mock_git.get_file_at_commit.return_value = "\x00BINARY_OR_TOO_LARGE:1234\x00"
        mock_git_cls.return_value = mock_git

        dv._enter_file_history("f.bin")
        assert "Binary file (1234 bytes)" in dv._content[0]

    @patch(_LOCALGIT_PATH)
    def test_shows_deleted_message(self, mock_git_cls):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content([
            "diff --git a/f.py b/f.py",
            "@@ -1,1 +0,0 @@",
            "-x",
        ])

        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [("sha0", "delete file")]
        mock_git.get_file_at_commit.return_value = None
        mock_git_cls.return_value = mock_git

        dv._enter_file_history("f.py")
        assert "File deleted in this commit" in dv._content[0]


class TestEscBehavior:
    """Esc key routing in different modes."""

    def test_esc_in_file_history_exits_to_diff(self):
        dv = DiffViewer()
        dv._file_history_mode = True
        dv._file_history_cache = {"sha": ["line"]}
        dv._saved_diff_state = MagicMock()
        dv._saved_diff_state.content = ["diff"]
        dv._saved_diff_state.diff_type = DiffType.COMMIT
        dv._saved_diff_state.scroll_i = 0
        dv._saved_diff_state.come_from = None

        dv._leave_display()
        assert dv._file_history_mode is False
        assert len(dv._file_history_cache) == 0

    def test_esc_in_hunk_mode_exits_hunk_mode(self):
        dv = DiffViewer()
        dv._hunk_mode = True
        dv._file_history_mode = False
        dv.come_from = None

        dv._leave_display()
        assert dv._hunk_mode is False

    def test_esc_in_diff_goes_back(self):
        dv = DiffViewer()
        dv._hunk_mode = False
        dv._file_history_mode = False
        target = MagicMock()
        dv.come_from = target

        with patch.object(dv, "emit") as mock_emit:
            dv._leave_display()
            mock_emit.assert_called_once()
