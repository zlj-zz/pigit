"""Tests for DiffViewer local word-diff support."""

from __future__ import annotations

from pigit.app_diff import DiffViewer


class TestWordDiffRanges:
    """Word-level diff ranges via difflib.SequenceMatcher."""

    def test_range_no_change(self):
        del_r, add_r = DiffViewer._word_diff_ranges("hello world", "hello world")
        assert del_r == []
        assert add_r == []

    def test_range_word_replace(self):
        del_r, add_r = DiffViewer._word_diff_ranges("hello world", "hello new")
        assert del_r == [(6, 11)]  # "world"
        assert add_r == [(6, 9)]   # "new"

    def test_range_multiple_word_changes(self):
        del_r, add_r = DiffViewer._word_diff_ranges(
            "old hello world tail",
            "new hello earth tail",
        )
        # "old " vs "new ", "world" vs "earth"
        assert len(del_r) == 2
        assert len(add_r) == 2

    def test_range_addition_at_end(self):
        del_r, add_r = DiffViewer._word_diff_ranges("foo", "foo bar")
        assert add_r == [(3, 7)]

    def test_range_deletion_at_end(self):
        del_r, add_r = DiffViewer._word_diff_ranges("foo bar", "foo")
        assert del_r == [(3, 7)]


class TestWordBoundaryTokenization:
    """GitHub-style word-boundary splits produce fine-grained tokens."""

    def test_punctuation_splits(self):
        """``foo.bar()`` → ``["foo", ".", "bar", "(", ")"]``."""
        del_r, add_r = DiffViewer._word_diff_ranges(
            "func foo.bar()", "func fooBar()"
        )
        # ".bar()" → "Bar()": only the changed sub-range highlighted.
        assert del_r == [(5, 12)]  # "foo.bar"
        assert add_r == [(5, 11)]  # "fooBar"

    def test_camelCase_not_split(self):
        """Word characters [a-zA-Z0-9_] stay together."""
        del_r, add_r = DiffViewer._word_diff_ranges("fooBar", "fooBaz")
        assert del_r == [(0, 6)]
        assert add_r == [(0, 6)]

    def test_multiple_punctuation_changes(self):
        del_r, add_r = DiffViewer._word_diff_ranges(
            "x = a + b",
            "x = a - b",
        )
        # "+" changed to "-", other tokens same.
        assert del_r == [(6, 7)]
        assert add_r == [(6, 7)]


class TestRangesToSegments:
    """Convert diff ranges into (text, kind, width) segments."""

    def test_no_ranges_all_unchanged(self):
        segs = DiffViewer._ranges_to_segments("hello world", [], "del")
        assert segs == [("hello world", None, 11)]

    def test_single_delete_middle(self):
        segs = DiffViewer._ranges_to_segments("hello old world", [(6, 9)], "del")
        assert len(segs) == 3
        assert segs[0] == ("hello ", None, 6)
        assert segs[1] == ("old", "del", 3)
        assert segs[2] == (" world", None, 6)

    def test_single_add_middle(self):
        segs = DiffViewer._ranges_to_segments("hello new world", [(6, 9)], "add")
        assert segs[1] == ("new", "add", 3)


class TestSetContentLocalWordDiff:
    """set_content with _word_diff=True computes segments from normal unified diff."""

    def _simple_diff(self):
        return [
            "diff --git a/f.py b/f.py",
            "--- a/f.py",
            "+++ b/f.py",
            "@@ -1,2 +1,2 @@",
            " context",
            "-old hello world",
            "+old new world",
        ]

    def test_content_unchanged_by_word_diff(self):
        dv = DiffViewer(word_diff=True)
        dv.set_content(self._simple_diff())
        # Content stays exactly the same as input (normal unified diff).
        assert dv._content[5] == "-old hello world"
        assert dv._content[6] == "+old new world"

    def test_segments_highlight_changed_words(self):
        dv = DiffViewer(word_diff=True)
        dv.set_content(self._simple_diff())

        del_segs = dv._word_diff_segments[5]
        add_segs = dv._word_diff_segments[6]

        # The changed word "hello" (del) and "new" (add) should be highlighted.
        del_changed = [s for s in del_segs if s[1] == "del"]
        add_changed = [s for s in add_segs if s[1] == "add"]
        assert del_changed == [("hello", "del", 5)]
        assert add_changed == [("new", "add", 3)]

    def test_hunks_still_parse_correctly(self):
        dv = DiffViewer(word_diff=True)
        dv.set_content(self._simple_diff())
        assert len(dv._hunks) == 1
        hunk = dv._hunks[0]
        assert hunk.old_count == 2
        assert hunk.new_count == 2
        assert hunk.start == 3  # @@ line index

    def test_patch_extraction_works(self):
        dv = DiffViewer(word_diff=True)
        dv.set_content(self._simple_diff())
        patch = dv._extract_hunk_patch(0)
        assert "-old hello world" in patch
        assert "+old new world" in patch

    def test_unpaired_lines_no_word_diff(self):
        """Pure additions / deletions get no word-diff (line bg is enough)."""
        dv = DiffViewer(word_diff=True)
        dv.set_content([
            "diff --git a/f.py b/f.py",
            "@@ -1,2 +1,3 @@",
            " ctx",
            "-old1",
            "-old2",
            "+new1",
        ])
        # old1 paired (with new1), old2 unpaired -> no word-diff segments.
        assert dv._word_diff_segments[4] == []  # unpaired "-old2"

    def test_help_entries_no_w_key(self):
        dv = DiffViewer()
        entries = dv.get_help_entries()
        keys = [k for k, _ in entries]
        assert "w" not in keys


class TestPreTokenizeWithWordDiff:
    """Word-diff segments receive per-token background colors."""

    def test_word_diff_segments_get_background(self):
        from pigit.app_theme import THEME
        from pigit.termui import SyntaxTokenizer

        tokenizer = SyntaxTokenizer()
        content = ["+foo bar baz"]
        segments: list[list[tuple[str, str | None, int]]] = [
            [
                ("foo ", None, 4),
                ("bar", "add", 3),
                (" baz", None, 4),
            ]
        ]
        tokens = DiffViewer._pre_tokenize_with(
            content, ["plain"], [None], tokenizer, segments
        )

        bar_tokens = [t for t in tokens[0] if t[0] == "bar"]
        assert bar_tokens
        assert bar_tokens[0][3] == THEME.bg_word_diff_add
        # Plain segments have no background.
        assert all(t[3] is None for t in tokens[0] if t[0] in ("foo ", " baz"))

    def test_del_segment_gets_delete_background(self):
        from pigit.app_theme import THEME
        from pigit.termui import SyntaxTokenizer

        tokenizer = SyntaxTokenizer()
        content = ["-foo bar"]
        segments: list[list[tuple[str, str | None, int]]] = [
            [("foo ", None, 4), ("bar", "del", 3)]
        ]
        tokens = DiffViewer._pre_tokenize_with(
            content, ["plain"], [None], tokenizer, segments
        )

        bar_tokens = [t for t in tokens[0] if t[0] == "bar"]
        assert bar_tokens
        assert bar_tokens[0][3] == THEME.bg_word_diff_del


class TestDrawTokensWithPerTokenBackground:
    """_draw_tokens honours per-token background override."""

    def test_token_background_overrides_line_background(self):
        from pigit.termui._surface import Surface
        from pigit.app_theme import THEME

        dv = DiffViewer()
        surface = Surface(20, 1)
        tokens = [
            ("a", THEME.fg_primary, 1, THEME.bg_word_diff_add),
            ("b", THEME.fg_primary, 1, None),
        ]
        dv._draw_tokens(surface, 0, 0, 20, tokens, bg=THEME.bg_diff_context)

        assert surface._rows[0][0].char == "a"
        assert surface._rows[0][1].char == "b"
        assert surface._rows[0][0].bg == THEME.bg_word_diff_add
        assert surface._rows[0][1].bg == THEME.bg_diff_context
