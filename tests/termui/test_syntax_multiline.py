# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_syntax_multiline.py
Description: scan_multiline whole-file state machine (string/comment/conflict
awareness) and conflict_kind classification for diff highlighting.
Author: Zev
Date: 2026-09-08
"""

from __future__ import annotations

import pytest

from pigit.diff_content import DiffContent
from pigit.termui.syntax import (
    SyntaxTokenizer,
    conflict_kind,
    scan_multiline,
    tracks_multiline,
)


def _never(_line: str) -> bool:
    """Reset predicate for contiguous whole-file scans."""
    return False


def _at_hunk(line: str) -> bool:
    return line.startswith("@@ ")


# ── language enablement (single-source predicate) ──


def test_tracks_multiline_sources():
    assert tracks_multiline("go") is True
    assert tracks_multiline("ts") is True  # alias → js
    assert tracks_multiline("cpp") is True  # alias → c
    assert tracks_multiline("py") is True
    assert tracks_multiline("plain") is False
    assert tracks_multiline("generic") is False
    assert tracks_multiline("sh") is False


# ── regression #1: strings hide block openers ──


def test_go_string_with_block_opener_does_not_open():
    """`/*` inside go backtick / double-quoted strings never opens a block."""
    lines = [
        "package main",
        "",
        'var tmpl = `prefix /* http://x/y` + "`" + ` suffix`',
        "",
        'const path = "/v1/*"',
        "",
        "func main() {",
        "\tprintln(path)",
        "}",
    ]
    assert (
        scan_multiline(lines, "go", strip_prefix=False, reset_lines=_never)
        == [None] * 9
    )


def test_line_comment_hides_block_opener():
    """`// http://a/*b` — the URL's `/*` is inside a line comment."""
    lines = [
        "// http://a/*b",
        "code();",
    ]
    assert scan_multiline(lines, "go", strip_prefix=False, reset_lines=_never) == [
        None,
        None,
    ]


def test_hash_comment_line_never_opens_block():
    """`# x /* y` — py has no block comments; a hash line stays code."""
    lines = [
        "# x /* y",
        "x = 1",
    ]
    assert scan_multiline(lines, "py", strip_prefix=False, reset_lines=_never) == [
        None,
        None,
    ]


# ── real block-comment tracking ──


def test_block_comment_opens_and_closes():
    lines = [
        "int main() {",
        "    /* banner",
        "       still inside",
        "       done */ int x;",
        "    return 0;",
    ]
    assert scan_multiline(lines, "c", strip_prefix=False, reset_lines=_never) == [
        None,
        "comment",
        "comment",
        "comment",
        None,
    ]


def test_same_line_close_then_reopen():
    lines = [
        "int a = f(); /* closed */ int b = g();",
        "    /* reopen",
        "    still open */",
        "done();",
    ]
    assert scan_multiline(lines, "c", strip_prefix=False, reset_lines=_never) == [
        None,
        "comment",
        "comment",
        None,
    ]


def test_diff_prefix_stripped_before_scan():
    lines = ["+int main() {", "+    /* banner", "+       still */", "+done();"]
    assert scan_multiline(lines, "c", strip_prefix=True, reset_lines=_never) == [
        None,
        "comment",
        "comment",
        None,
    ]


def test_untracked_language_yields_all_none():
    lines = ["+/* whatever", "+   still open"]
    assert scan_multiline(lines, "sh", strip_prefix=True, reset_lines=_never) == [
        None,
        None,
    ]


# ── py docstrings ──


def test_py_docstring_opens_and_closes():
    lines = [
        "+def foo():",
        '+    """doc',
        '+    more"""',
        "+x = 1",
    ]
    assert scan_multiline(lines, "py", strip_prefix=True, reset_lines=_never) == [
        None,
        "docstring",
        "docstring",
        None,
    ]


def test_py_docstring_missing_closer_at_eof():
    lines = ["+x = 1", '+    """never closed']
    assert scan_multiline(lines, "py", strip_prefix=True, reset_lines=_never) == [
        None,
        "docstring",
    ]


def test_py_docstring_single_line_does_not_open():
    lines = ['+    """one liner"""', "+x = 2"]
    assert scan_multiline(lines, "py", strip_prefix=True, reset_lines=_never) == [
        None,
        None,
    ]


def test_py_docstring_resets_on_hunk_boundary():
    """A hunk boundary resets docstring state (fragment is not contiguous)."""
    lines = [
        "+def a():",
        '+    """doc',
        "@@ -10 +12 @@",
        "+    still open",
    ]
    assert scan_multiline(lines, "py", strip_prefix=True, reset_lines=_at_hunk) == [
        None,
        "docstring",
        None,
        None,
    ]


def test_no_newline_marker_is_transparent():
    lines = [
        '+    """doc',
        "\\ No newline at end of file",
        '+    end"""',
    ]
    assert scan_multiline(lines, "py", strip_prefix=True, reset_lines=_never) == [
        "docstring",
        None,
        "docstring",
    ]


def test_conflict_marker_lines_do_not_open_blocks():
    """Merge markers neither open nor close multi-line state."""
    lines = [
        "/* ours banner",  # opens (unresolved ours side)
        "<<<<<<< HEAD",  # marker — state unchanged, still in block
        "=======",
        ">>>>>>> theirs",
        "   still inside */",  # closer
        "done();",
    ]
    assert scan_multiline(lines, "go", strip_prefix=False, reset_lines=_never) == [
        "comment",
        "comment",
        "comment",
        "comment",
        "comment",
        None,
    ]


# ── conflict_kind ──


@pytest.mark.parametrize(
    "code, expected",
    [
        ("<<<<<<< HEAD", "conflict_ours"),
        ("<<<<<<<", "conflict_ours"),
        ("=======", "conflict_sep"),
        (">>>>>>> theirs (x)", "conflict_theirs"),
        (">>>>>>>", "conflict_theirs"),
        ("<<<<<<<< HEAD", None),  # 8 chars — not a marker
        ("========", None),  # md setext underline
        ("======", None),
        ("+<<<<<<< HEAD", None),  # diff prefix not stripped by the caller
        ("x = 1", None),
        ("", None),
    ],
)
def test_conflict_kind(code: str, expected: str | None):
    assert conflict_kind(code) == expected


# ── rendering: conflict markers win over the lexer ──


def test_conflict_marker_renders_as_conflict_token():
    """`+<<<<<<< HEAD` renders as one conflict-colored token, never lexed."""
    tok = SyntaxTokenizer()
    lines = [
        "diff --git a/f.py b/f.py",
        "index 0000000..1111111 100644",
        "--- /dev/null",
        "+++ b/f.py",
        "+<<<<<<< HEAD",
        "+=======",
        "+>>>>>>> theirs",
    ]
    doc = DiffContent.from_diff_lines(lines, word_diff=False, tokenizer=tok)
    rendered = DiffContent.pre_tokenize_with(
        doc.lines, doc.line_langs, doc.multiline_mask, tok
    )
    conflict_fg = tok.resolve_color("conflict", "py")
    for i, raw in ((4, "+<<<<<<< HEAD"), (5, "+======="), (6, "+>>>>>>> theirs")):
        code = raw[1:]
        line_tokens = rendered[i]
        assert [(text, fg) for text, fg, *_ in line_tokens] == [(code, conflict_fg)]
