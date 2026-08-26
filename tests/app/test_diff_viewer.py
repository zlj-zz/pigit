"""Tests for DiffViewer file history mode."""

from unittest.mock import MagicMock, patch

import pytest

from pigit.app_diff import DiffViewer, DiffType

_LOCALGIT_PATH = "pigit.git.api.GitApi"


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
        dv.scroll_i = 4  # cursor on the + line, inside the hunk
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
        dv.scroll_i = 4
        assert dv._current_file_path() == "path with spaces"

    def test_returns_none_when_no_hunk(self):
        dv = DiffViewer()
        dv.scroll_i = 0
        assert dv._current_file_path() is None

    def test_returns_none_for_malformed_header(self):
        lines = [
            "not a diff header",
            "some content",
        ]
        dv = self._viewer_with_diff(lines)
        dv.scroll_i = 1
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
        dv.set_content(
            [
                "diff --git a/src/main.py b/src/main.py",
                "--- a/src/main.py",
                "+++ b/src/main.py",
                "@@ -1,3 +1,3 @@",
                " old_line",
                "-removed",
                "+added",
            ]
        )
        dv.scroll_i = 2
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

        original_content = list(viewer._lines)
        viewer._enter_file_history("src/main.py")
        assert viewer._lines != original_content

        viewer._exit_file_history()

        assert viewer._file_history_mode is False
        assert viewer._lines == original_content
        assert viewer._diff_type == DiffType.COMMIT
        assert viewer.scroll_i == 2

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
            assert viewer.scroll_i == 2


class TestFileHistoryNavigation:
    """p/n navigation between file history commits."""

    @pytest.fixture
    def viewer_in_history(self):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,1 +1,1 @@",
                " old",
            ]
        )

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
        dv.scroll_i = 2

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


class TestFileHistoryCache:
    """LRU caching of file content."""

    @patch(_LOCALGIT_PATH)
    def test_cache_hits_avoid_repeated_git_calls(self, mock_git_cls):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,1 +1,1 @@",
                " x",
            ]
        )

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
        dv.set_content(
            [
                "diff --git a/f.bin b/f.bin",
                "@@ -1,1 +1,1 @@",
                " x",
            ]
        )

        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [("sha0", "add binary")]
        mock_git.get_file_at_commit.return_value = "\x00BINARY_OR_TOO_LARGE:1234\x00"
        mock_git_cls.return_value = mock_git

        dv._enter_file_history("f.bin")
        assert "Binary file (1234 bytes)" in dv._lines[0]

    @patch(_LOCALGIT_PATH)
    def test_shows_deleted_message(self, mock_git_cls):
        dv = DiffViewer()
        dv._repo_path = "/fake/repo"
        dv._diff_type = DiffType.COMMIT
        dv.i_cache_key = "sha0"
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,1 +0,0 @@",
                "-x",
            ]
        )

        mock_git = MagicMock()
        mock_git.get_file_history.return_value = [("sha0", "delete file")]
        mock_git.get_file_at_commit.return_value = None
        mock_git_cls.return_value = mock_git

        dv._enter_file_history("f.py")
        assert "File deleted in this commit" in dv._lines[0]


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


class TestEmptyContentChrome:
    """Empty DiffViewer still draws box chrome (preview void is not a blank hole)."""

    def test_empty_content_draws_box(self):
        from pigit.termui.surface import Surface

        dv = DiffViewer()
        dv.set_box_title("")
        dv.set_content([])
        dv.resize((40, 12))
        surface = Surface(40, 12)
        dv.paint(surface)
        rows = surface.rows()
        assert rows[0][0].char == "\u250c"  # ┌
        assert rows[0][-1].char == "\u2510"  # ┐
        assert rows[-1][0].char == "\u2514"  # └
        assert rows[-1][-1].char == "\u2518"  # ┘


class TestContentInstallInvariants:
    """Content replace must be atomic and invalidate pending tokenize."""

    def test_stale_diff_tokenize_does_not_overwrite_plain(self):
        """File-history plain load must drop pending diff tokenize callbacks."""
        dv = DiffViewer()
        captured: dict[str, object] = {}

        def capture_start(work, callback):
            captured["callback"] = callback

        with patch.object(dv._tokenize_task, "start", side_effect=capture_start):
            dv.set_content(
                [
                    "diff --git a/f.py b/f.py",
                    "--- a/f.py",
                    "+++ b/f.py",
                    "@@ -1 +1 @@",
                    "-old",
                    "+new",
                ]
            )

        assert "callback" in captured
        dv._file_history_path = "f.py"
        dv._set_plain_content(["line-a", "line-b", "line-c"])
        plain_tokens = list(dv._render_tokens)
        assert len(plain_tokens) == 3

        with patch.object(dv, "is_mounted", return_value=True):
            stale = [[("DIFF-ONLY", (255, 0, 0), 9, None)]] * 52
            captured["callback"](stale)  # type: ignore[operator]

        assert dv._render_tokens == plain_tokens
        assert dv._lines == ["line-a", "line-b", "line-c"]

    def test_parse_failure_keeps_previous_consistent_state(self):
        """Failed set_content must not clear tokens while leaving old structure."""
        dv = DiffViewer()
        with patch.object(dv._tokenize_task, "start"):
            dv.set_content(["+kept"])
        dv._render_tokens = [[("kept", (200, 200, 200), 4, None)]]
        content_before = list(dv._lines)
        tokens_before = list(dv._render_tokens)
        hunks_before = list(dv._hunks)

        with pytest.raises(TypeError):
            dv.set_content([123])  # type: ignore[list-item]

        assert dv._lines == content_before
        assert dv._render_tokens == tokens_before
        assert dv._hunks == hunks_before

    def test_file_history_tokens_fallback_when_shorter_than_content(self):
        """Short _render_tokens must not blank file-history lines."""
        from pigit.termui.surface import Surface

        dv = DiffViewer()
        dv._file_history_mode = True
        dv._file_history_path = "f.py"
        dv._file_history_commits = [("abc1234", "msg")]
        dv._file_history_index = 0
        dv._set_plain_content(["alpha", "beta", "gamma"])
        dv._render_tokens = dv._render_tokens[:1]
        dv.resize((40, 12))
        surface = Surface(40, 12)
        dv.paint(surface)
        text = "".join(cell.char for cell in surface.rows()[3])
        assert "gamma" in text

    def test_heatmap_at_guards_short_heatmap(self):
        from pigit.app_theme import THEME

        dv = DiffViewer()
        dv.set_content(["+x"])
        dv._heatmap = []
        dv._heatmap_colors = []
        assert dv._heatmap_at(0) == (" ", THEME.fg_dim)

    def test_init_has_no_dummy_doc(self):
        dv = DiffViewer()
        assert not hasattr(dv, "_doc")
        assert dv._lines == []
        assert dv._render_tokens == []


def test_diff_viewer_owns_line_state() -> None:
    d = DiffViewer(id="diff")
    assert not hasattr(d, "_browser")
    d.set_content(["+a", "-b"])
    assert d._lines[0].startswith("+")


def test_diff_viewer_forwards_scroll_up_down() -> None:
    d = DiffViewer(id="diff")
    d.resize((40, 10))
    d.set_content([f"line {i}" for i in range(40)])
    d.scroll_down(3)
    assert d.scroll_i == 3
    d.scroll_up(1)
    assert d.scroll_i == 2


def test_hunk_jump_beyond_clamped_viewport_resolves_path() -> None:
    """Hunk past max viewport line must not clamp _line_i (path badge / v)."""
    lines = [
        "diff --git a/a.py b/a.py",
        "--- a/a.py",
        "+++ b/a.py",
        "@@ -1,30 +1,30 @@",
    ]
    lines.extend(f" ctx-a-{i}" for i in range(30))
    lines.extend(
        [
            "diff --git a/b.py b/b.py",
            "--- a/b.py",
            "+++ b/b.py",
            "@@ -1,2 +1,2 @@",
            "+b1",
            "+b2",
        ]
    )
    dv = DiffViewer()
    dv.resize((40, 6))
    dv.set_content(lines)
    assert dv._max_viewport_i() == len(lines) - dv._viewport_rows
    dv.scroll_i = 0
    dv._next_hunk()  # first hunk header
    assert dv._current_file_path() == "a.py"
    dv._next_hunk()  # second file hunk — beyond clamped browser scroll
    assert dv.scroll_i > dv._max_viewport_i()
    assert dv._current_file_path() == "b.py"


def test_hunk_navigation_reaches_eof_hunks() -> None:
    """] must advance through late hunks even when headers exceed max viewport."""
    lines = [f"pad-{i}" for i in range(100)]
    lines[4] = "@@ hunk-a"
    lines[85] = "@@ hunk-b"
    lines[95] = "@@ hunk-c"
    dv = DiffViewer()
    dv.resize((80, 20))
    dv.set_content(lines)
    dv.scroll_i = 0
    dv._next_hunk()
    assert dv.scroll_i == 4
    dv._next_hunk()
    assert dv.scroll_i == 85
    dv._next_hunk()
    assert dv.scroll_i == 95


def test_line_i_survives_resize_after_pre_resize_assignment() -> None:
    """Logical line index survives resize; Diff owns scroll state directly."""
    dv = DiffViewer()
    dv.set_content([f"line {i}" for i in range(100)])
    dv.scroll_i = 85
    dv.resize((80, 20))
    assert dv.scroll_i == 85
    assert dv._max_viewport_i() == 82
