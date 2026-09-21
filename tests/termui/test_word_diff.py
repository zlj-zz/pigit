"""Tests for DiffContent / DiffViewer local word-diff support."""

from __future__ import annotations

from pigit.app_diff import DiffViewer
from pigit.diff_content import DiffContent
from pigit.termui import palette


class TestWordDiffRanges:
    """Word-level diff ranges via difflib.SequenceMatcher."""

    def test_range_no_change(self):
        del_r, add_r = DiffContent.word_diff_ranges("hello world", "hello world")
        assert del_r == []
        assert add_r == []

    def test_range_word_replace(self):
        del_r, add_r = DiffContent.word_diff_ranges("hello world", "hello new")
        assert del_r == [(6, 11)]  # "world"
        assert add_r == [(6, 9)]  # "new"

    def test_range_multiple_word_changes(self):
        del_r, add_r = DiffContent.word_diff_ranges(
            "old hello world tail",
            "new hello earth tail",
        )
        # "old " vs "new ", "world" vs "earth"
        assert len(del_r) == 2
        assert len(add_r) == 2

    def test_range_addition_at_end(self):
        """The separating space is not part of the added word."""
        del_r, add_r = DiffContent.word_diff_ranges("foo", "foo bar")
        assert add_r == [(4, 7)]

    def test_range_deletion_at_end(self):
        del_r, add_r = DiffContent.word_diff_ranges("foo bar", "foo")
        assert del_r == [(4, 7)]

    def test_indentation_only_change_marks_nothing(self):
        del_r, add_r = DiffContent.word_diff_ranges(
            "        return 1", "            return 1"
        )
        assert (del_r, add_r) == ([], [])


class TestWordTokenization:
    """Whitespace-delimited words, matching ``git diff --word-diff``."""

    def test_dotted_name_is_one_word(self):
        """``foo.bar()`` is a single word, so it changes as a whole."""
        del_r, add_r = DiffContent.word_diff_ranges("func foo.bar()", "func fooBar()")
        assert del_r == [(5, 14)]  # "foo.bar()"
        assert add_r == [(5, 13)]  # "fooBar()"

    def test_camelCase_not_split(self):
        """Word characters [a-zA-Z0-9_] stay together."""
        del_r, add_r = DiffContent.word_diff_ranges("fooBar", "fooBaz")
        assert del_r == [(0, 6)]
        assert add_r == [(0, 6)]

    def test_multiple_punctuation_changes(self):
        del_r, add_r = DiffContent.word_diff_ranges(
            "x = a + b",
            "x = a - b",
        )
        # "+" changed to "-", other tokens same.
        assert del_r == [(6, 7)]
        assert add_r == [(6, 7)]


class TestRangesToSegments:
    """Convert diff ranges into (text, kind, width) segments."""

    def test_no_ranges_all_unchanged(self):
        segs = DiffContent.ranges_to_segments("hello world", [], "del")
        assert segs == [("hello world", None, 11)]

    def test_single_delete_middle(self):
        segs = DiffContent.ranges_to_segments("hello old world", [(6, 9)], "del")
        assert len(segs) == 3
        assert segs[0] == ("hello ", None, 6)
        assert segs[1] == ("old", "del", 3)
        assert segs[2] == (" world", None, 6)

    def test_single_add_middle(self):
        segs = DiffContent.ranges_to_segments("hello new world", [(6, 9)], "add")
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
        assert dv._lines[5] == "-old hello world"
        assert dv._lines[6] == "+old new world"

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

    def test_one_sided_runs_get_no_word_diff(self):
        """No counterpart means nothing to compare: line bg marks the change."""
        inserted = DiffViewer(word_diff=True)
        inserted.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,1 +1,3 @@",
                " ctx",
                "+new1",
                "+new2",
            ]
        )
        for idx in (3, 4):
            assert [s for s in inserted._word_diff_segments[idx] if s[1]] == []

        deleted = DiffViewer(word_diff=True)
        deleted.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,3 +1,1 @@",
                "-gone1",
                "-gone2",
                " ctx",
            ]
        )
        for idx in (2, 3):
            assert [s for s in deleted._word_diff_segments[idx] if s[1]] == []

    def test_only_changed_words_are_marked(self):
        """Matched words stay unmarked even when most of the line changed."""
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,1 +1,1 @@",
                "-resp.BaseModel.BaseCode = 400",
                "+resp.SkipCode = skipCodeContractNotMatched",
            ]
        )
        removed = [t for t, k, _ in dv._word_diff_segments[2] if k == "del"]
        added = [t for t, k, _ in dv._word_diff_segments[3] if k == "add"]
        assert " = " not in "".join(removed)  # shared text stays unmarked
        assert " = " not in "".join(added)
        assert "".join(removed).strip() and "".join(added).strip()

    def test_unequal_run_diffs_as_one_stream(self):
        """Removals and additions in a run diff as one text stream.

        Pairing by index would compare "y = 2" with "x2 = 101"; the stream
        keeps every word aligned with its counterpart instead.
        """
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,4 +1,4 @@",
                "-x = 1",
                "-y = 2",
                "-z = 3",
                "+x = 100",
                "+x2 = 101",
                "+y = 200",
            ]
        )

        def changed(i):
            return "".join(t for t, k, _ in dv._word_diff_segments[i] if k)

        assert changed(2) == "1"  # -x = 1
        assert changed(3) == "2"  # -y = 2  (not the whole line)
        assert changed(4) == "z = 3"  # -z = 3 replaced by the x2 line
        assert changed(5) == "100"
        assert changed(6) == "x2 = 101"
        assert changed(7) == "200"

    def test_groups_do_not_pair_across_context(self):
        """Two change runs in one hunk keep their own counterparts."""
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,5 +1,6 @@",
                " a = 1",
                "-b = 2",
                "+b = 20",
                "+b2 = 21",
                " c = 3",
                "-d = 4",
                "+d = 40",
                " e = 5",
            ]
        )

        def changed(i):
            return "".join(t for t, k, _ in dv._word_diff_segments[i] if k)

        assert changed(3) == "2"  # -b = 2 vs +b = 20
        assert changed(7) == "4"  # -d = 4 vs +d = 40 (not +b2 = 21)

    def test_huge_rewrite_skips_word_diff(self):
        """Wholesale rewrites stay bounded: only the line background marks them."""
        count = 300
        removed = [f"-value_{i} = compute({i})" for i in range(count)]
        added = [f"+value_{i} = compute({i + 1})" for i in range(count)]
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/b.py b/b.py",
                f"@@ -1,{count} +1,{count} @@",
                *removed,
                *added,
            ]
        )
        assert [t for segs in dv._word_diff_segments for t, k, _ in segs if k] == []

    def test_marks_never_include_leading_or_trailing_whitespace(self):
        """A range bridging two lines must not paint the next line's indent."""
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,3 +1,3 @@",
                "-    resp.BaseModel.BaseCode = 400",
                "-    resp.BaseModel.BaseMsg = reason",
                "+    resp.SkipCode = skipCodeContractNotMatched",
                "+    resp.SkipReason = reason",
            ]
        )
        for idx in (2, 3, 4, 5):
            for text, kind, _ in dv._word_diff_segments[idx]:
                if kind:
                    assert not text[:1].isspace(), (idx, text)
                    assert not text[-1:].isspace(), (idx, text)

    def test_whitespace_only_change_has_no_marks(self):
        """Indentation is not a word change (git word-diff semantics)."""
        dv = DiffViewer(word_diff=True)
        dv.set_content(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1,2 +1,2 @@",
                "-        return 1",
                "+            return 1",
            ]
        )
        for idx in (2, 3):
            assert [t for t, k, _ in dv._word_diff_segments[idx] if k] == []

    def test_help_entries_no_w_key(self):
        dv = DiffViewer()
        entries = dv.get_help_entries()
        keys = [k for k, _ in entries]
        assert "w" not in keys


class TestPreTokenizeWithWordDiff:
    """Word-diff segments receive per-token background colors."""

    def test_word_diff_segments_get_background(self):
        from pigit.app_theme import THEME
        from pigit.termui.syntax import SyntaxTokenizer

        tokenizer = SyntaxTokenizer()
        content = ["+foo bar baz"]
        segments: list[list[tuple[str, str | None, int]]] = [
            [
                ("foo ", None, 4),
                ("bar", "add", 3),
                (" baz", None, 4),
            ]
        ]
        tokens = DiffContent.pre_tokenize_with(
            content, ["plain"], [None], tokenizer, segments
        )

        bar_tokens = [t for t in tokens[0] if t[0] == "bar"]
        assert bar_tokens
        assert bar_tokens[0][3] == THEME.bg_word_diff_add
        # Plain segments have no background.
        assert all(t[3] is None for t in tokens[0] if t[0] in ("foo ", " baz"))

    def test_del_segment_gets_delete_background(self):
        from pigit.app_theme import THEME
        from pigit.termui.syntax import SyntaxTokenizer

        tokenizer = SyntaxTokenizer()
        content = ["-foo bar"]
        segments: list[list[tuple[str, str | None, int]]] = [
            [("foo ", None, 4), ("bar", "del", 3)]
        ]
        tokens = DiffContent.pre_tokenize_with(
            content, ["plain"], [None], tokenizer, segments
        )

        bar_tokens = [t for t in tokens[0] if t[0] == "bar"]
        assert bar_tokens
        assert bar_tokens[0][3] == THEME.bg_word_diff_del


class TestDrawTokensWithPerTokenBackground:
    """_draw_tokens honours per-token background override."""

    def test_token_background_overrides_line_background(self):
        from pigit.termui.surface import Surface
        from pigit.app_theme import THEME

        dv = DiffViewer()
        surface = Surface(20, 1)
        tokens = [
            ("a", THEME.fg_primary, 1, THEME.bg_word_diff_add, palette.STYLE_UNDERLINE),
            ("b", THEME.fg_primary, 1, None, 0),
        ]
        dv._draw_tokens(surface, 0, 0, 20, tokens, bg=THEME.bg_diff_context)

        assert surface._rows[0][0].char == "a"
        assert surface._rows[0][1].char == "b"
        assert surface._rows[0][0].bg == THEME.bg_word_diff_add
        assert surface._rows[0][1].bg == THEME.bg_diff_context
