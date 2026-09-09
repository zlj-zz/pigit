# -*- coding: utf-8 -*-
"""
Module: tests/app/test_diff_content_sources.py
Description: Full-file side sources for the diff multi-line mask —
diff_line_sides, from_diff_lines(sources=), parse_index_hashes, and the
viewer/preview loader wiring.
Author: Zev
Date: 2026-09-08
"""

from __future__ import annotations

import time
from unittest.mock import Mock, patch

from pigit.app_diff import DiffType, DiffViewer
from pigit.app_diff_preview import PreviewPanel
from pigit.diff_content import DiffContent, needs_full_source
from pigit.git.api import parse_index_hashes
from pigit.termui.async_task import AsyncTask
from pigit.termui.syntax import SyntaxTokenizer

_TOK = SyntaxTokenizer()

# Old/new go file: the /* opener is line 1, the body runs to line 19, the
# closer is line 20 — a -U3 hunk around a body change never sees the opener.
_OLD_GO = (
    ["/* banner"]
    + [f"   body {i}" for i in range(1, 19)]
    + [
        "*/",
        "func A() {}",
    ]
)
_CHANGED_AT = 14  # 1-based source line edited between sides
_NEW_GO = [
    line if i != _CHANGED_AT else "   body 14 edited"
    for i, line in enumerate(_OLD_GO, start=1)
]

_FRAGMENT = [
    "diff --git a/big.go b/big.go",
    "index 1111111..2222222 100644",
    "--- a/big.go",
    "+++ b/big.go",
    "@@ -12,7 +12,7 @@",
    "    body 11",
    "    body 12",
    "    body 13",
    "-   body 14",
    "+   body 14 edited",
    "    body 15",
    "    body 16",
    "    body 17",
]

_SOURCES = {"big.go": (_OLD_GO, _NEW_GO)}

# Content line indices of the fragment (0-based): 5..11 are the hunk body.
_HUNK_LINES = range(5, 12)


# ── test 6: side sources fix the truncated-fragment mask ──


def test_fragment_fallback_misses_opener_outside_hunk():
    """Symptom #2 baseline: without sources the body lines are unmasked."""
    doc = DiffContent.from_diff_lines(_FRAGMENT, word_diff=False, tokenizer=_TOK)
    for i in _HUNK_LINES:
        assert doc.multiline_mask[i] is None


def test_sources_mask_comment_body_even_with_opener_outside_hunk():
    doc = DiffContent.from_diff_lines(
        _FRAGMENT, word_diff=False, tokenizer=_TOK, sources=_SOURCES
    )
    # Every hunk body line is inside the real /* … */ block on both sides.
    for i in _HUNK_LINES:
        assert doc.multiline_mask[i] == "comment"


def test_sources_restore_code_after_closer():
    """Lines after the real ``*/`` are code again (no over-dim)."""
    old_file = ["/* banner", "   body", "*/", "func A() {}"]
    new_file = ["/* banner", "   body edited", "   extra", "*/", "func A() {}"]
    fragment = [
        "diff --git a/f.go b/f.go",
        "index 1111111..2222222 100644",
        "--- a/f.go",
        "+++ b/f.go",
        "@@ -1,4 +1,5 @@",
        " /* banner",
        "-   body",
        "+   body edited",
        "+   extra",
        " */",
        " func A() {}",
    ]
    doc = DiffContent.from_diff_lines(
        fragment,
        word_diff=False,
        tokenizer=_TOK,
        sources={"f.go": (old_file, new_file)},
    )
    # rows: 5=opener(comment), 6/7/8=body(comment), 9=closer(comment),
    # 10=func(code — the real */ closed the block before it).
    assert doc.multiline_mask[5:9] == ["comment"] * 4
    assert doc.multiline_mask[9] == "comment"
    assert doc.multiline_mask[10] is None


def test_needs_full_source_matches_scanner_enablement():
    assert needs_full_source("go") is True
    assert needs_full_source("ts") is True
    assert needs_full_source("py") is True
    assert needs_full_source("plain") is False
    assert needs_full_source("sh") is False


# ── test 7: staged-conflict diff against the marker-carrying index blob ──


def test_staged_conflict_sources_mask_and_render():
    """Markers stay neutral in the scan and render as conflict tokens."""
    new_file = [
        "package main",
        "<<<<<<< HEAD",
        "/* ours banner",
        "=======",
        "/* theirs banner",
        ">>>>>>> theirs",
        "   body */",
        "func A() {}",
    ]
    fragment = [
        "diff --git a/s.go b/s.go",
        "index 1111111..2222222 100644",
        "--- a/s.go",
        "+++ b/s.go",
        "@@ -1,8 +1,8 @@",
        " package main",
        "+<<<<<<< HEAD",
        "+/* ours banner",
        "+=======",
        "+/* theirs banner",
        "+>>>>>>> theirs",
        "+   body */",
        "+func A() {}",
    ]
    doc = DiffContent.from_diff_lines(
        fragment,
        word_diff=False,
        tokenizer=_TOK,
        sources={"s.go": (None, new_file)},
    )
    # Scan mask: markers are neutral; the ours banner opens (unresolved
    # intermediate state) and ``body */`` closes it.
    assert doc.multiline_mask[6] is None  # +<<<<<<< HEAD
    assert doc.multiline_mask[7] == "comment"  # +/* ours banner
    assert doc.multiline_mask[8] == "comment"  # +=======
    assert doc.multiline_mask[9] == "comment"  # +/* theirs banner
    assert doc.multiline_mask[10] == "comment"  # +>>>>>>> theirs
    # ``body */`` sits inside the theirs comment; the closer line counts as
    # comment (existing semantics) and closes the block before ``func``.
    assert doc.multiline_mask[11] == "comment"
    assert doc.multiline_mask[12] is None  # +func A() {}

    # Render: markers render as conflict tokens, not lexed fragments.
    conflict_fg = _TOK.resolve_color("conflict", "py")
    rendered = DiffContent.pre_tokenize_with(
        doc.lines, doc.line_langs, doc.multiline_mask, _TOK
    )
    for idx in (6, 8, 10):
        code = doc.lines[idx][1:]
        assert [(text, fg) for text, fg, *_ in rendered[idx]] == [(code, conflict_fg)]


# ── test 8: parse_index_hashes ──


def test_parse_index_hashes_variable_abbrev():
    assert parse_index_hashes("index 1234567..89abcde 100644") == (
        "1234567",
        "89abcde",
    )
    assert parse_index_hashes("index aabbccdd..eeff0011 100644") == (
        "aabbccdd",
        "eeff0011",
    )


def test_parse_index_hashes_zero_sides_map_to_none():
    assert parse_index_hashes("index 0000000..e69de29") == (None, "e69de29")
    assert parse_index_hashes("index e69de29..0000000") == ("e69de29", None)
    assert parse_index_hashes("index 0000000..0000000") == (None, None)


def test_parse_index_hashes_no_index_line():
    assert parse_index_hashes("diff --git a/x b/x") is None
    assert parse_index_hashes("--- a/x") is None
    assert parse_index_hashes("") is None


# ── test 9: diff_line_sides ──


def test_diff_line_sides_counters_and_headers():
    content = [
        "diff --git a/f b/f",
        "index 111..222",
        "--- a/f",
        "+++ b/f",
        "@@ -4,3 +4,3 @@",
        " ctx",  # old 4 / new 4
        "-old line",  # old 5
        "+new line",  # new 5
        " ctx2",  # old 6 / new 6
        "\\ No newline at end of file",
    ]
    sides = DiffContent.diff_line_sides(content)
    assert sides[0:4] == [(None, None)] * 4
    assert sides[4] == (None, None)  # @@ marker
    assert sides[5] == (4, 4)
    assert sides[6] == (5, None)
    assert sides[7] == (None, 5)
    assert sides[8] == (6, 6)
    assert sides[9] == (None, None)


def test_diff_line_sides_tolerates_malformed_hunk():
    """A malformed @@ header resets counters to 0 instead of raising."""
    content = [
        "@@ not-a-real-hunk",
        " ctx",
        "@@ -7,2 +7,2 @@",
        " ctx2",
    ]
    sides = DiffContent.diff_line_sides(content)
    assert sides[0] == (None, None)
    assert sides[1] == (0, 0)  # reset counters, context at 0/0
    assert sides[2] == (None, None)
    assert sides[3] == (7, 7)


def test_diff_line_sides_distinguishes_headers_from_minus_lines():
    """``--- `` file headers are not ``-`` content lines (counters untouched)."""
    sides = DiffContent.diff_line_sides(
        [
            "diff --git a/f b/f",
            "--- a/f",
            "@@ -1,1 +1,1 @@",
            "-real del",
        ]
    )
    assert sides[0] == (None, None)  # diff --git
    assert sides[1] == (None, None)  # --- file header, not a deletion
    assert sides[2] == (None, None)  # @@ marker
    assert sides[3] == (1, None)  # deletion at old line 1


# ── wiring: viewer loader + preview repo context (M2) ──


def _wait_for_loader(loader: Mock, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not loader.called and time.monotonic() < deadline:
        time.sleep(0.01)
    AsyncTask.poll_all()


def test_diff_viewer_loader_fetches_sources_in_worker():
    loader = Mock(return_value=(_OLD_GO, _NEW_GO))
    viewer = DiffViewer(source_loader=loader)
    viewer.set_repo_path("/work/repo")
    viewer.mount()
    viewer.set_content(_FRAGMENT)

    _wait_for_loader(loader)

    loader.assert_called_once_with(
        "/work/repo", "big.go", "1111111", "2222222", DiffType.UNSTAGED
    )
    # The worker-installed mask reflects the real side sources.
    for i in _HUNK_LINES:
        assert viewer._multiline_mask[i] == "comment"


def test_diff_viewer_without_loader_keeps_fragment_fallback():
    viewer = DiffViewer()
    viewer.set_repo_path("/work/repo")
    viewer.mount()
    viewer.set_content(_FRAGMENT)

    _wait_for_loader(Mock())  # no-op settle

    for i in _HUNK_LINES:
        assert viewer._multiline_mask[i] is None  # string-aware fragment mask


def test_preview_panel_passes_repo_context_to_loader():
    """M2: the preview viewer gets repo_path/diff_type and the shared loader."""
    loader = Mock(return_value=(_OLD_GO, _NEW_GO))
    preview = PreviewPanel(
        source_loader=loader,
        get_repo_path=lambda: "/work/repo",
    )
    preview.set_diff_type(DiffType.STAGED)
    preview.mount()
    preview.set_preview(_FRAGMENT, title="big.go")

    _wait_for_loader(loader)

    loader.assert_called_once_with(
        "/work/repo", "big.go", "1111111", "2222222", DiffType.STAGED
    )
    for i in _HUNK_LINES:
        assert preview._diff_viewer._multiline_mask[i] == "comment"
