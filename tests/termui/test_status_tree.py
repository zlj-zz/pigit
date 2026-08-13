# -*- coding: utf-8 -*-
"""Tests for status tree building pure functions."""

from pigit.app_status import build_status_tree, StatusTreeRow, _summarize
from pigit.git.model import File


def _file(name, short_status=" M", has_staged=False, has_unstaged=True):
    """Construct a File with the fields relevant to tree building."""
    return File(
        name=name,
        display_str=name,
        short_status=short_status,
        has_staged_change=has_staged,
        has_unstaged_change=has_unstaged,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )


def _paths(rows):
    """Return (kind, path, depth) triples for concise assertions."""
    return [(r.kind, r.path, r.depth) for r in rows]


def test_groups_files_by_directory():
    items = [(_file("src/a.py"), 0), (_file("src/b.py"), 1), (_file("README.md"), 2)]
    rows = build_status_tree(items, set())
    assert _paths(rows) == [
        ("dir", "src", 0),
        ("file", "src/a.py", 1),
        ("file", "src/b.py", 1),
        ("file", "README.md", 0),
    ]


def test_implicit_intermediate_dirs():
    """src/app/main.py must create both src/ and src/app/ nodes."""
    items = [(_file("src/app/main.py"), 0)]
    rows = build_status_tree(items, set())
    assert _paths(rows) == [
        ("dir", "src", 0),
        ("dir", "src/app", 1),
        ("file", "src/app/main.py", 2),
    ]


def test_root_files_at_top_level():
    items = [(_file("plain.txt"), 0)]
    rows = build_status_tree(items, set())
    assert _paths(rows) == [("file", "plain.txt", 0)]


def test_collapsed_dir_hides_children():
    items = [(_file("src/a.py"), 0), (_file("src/deep/b.py"), 1)]
    rows = build_status_tree(items, {"src"})
    # src/ is rendered but its children (a.py and deep/) are hidden.
    assert _paths(rows) == [("dir", "src", 0)]


def test_collapse_subdir_keeps_siblings():
    items = [
        (_file("src/a.py"), 0),
        (_file("src/deep/b.py"), 1),
    ]
    rows = build_status_tree(items, {"src/deep"})
    # Same level: directories before files; deep/ is collapsed but rendered.
    assert _paths(rows) == [
        ("dir", "src", 0),
        ("dir", "src/deep", 1),
        ("file", "src/a.py", 1),
    ]


def test_source_index_preserved():
    items = [(_file("src/a.py"), 5), (_file("src/b.py"), 9)]
    rows = build_status_tree(items, set())
    file_rows = [r for r in rows if r.kind == "file"]
    assert [r.source_index for r in file_rows] == [5, 9]
    # Directory row has no source index.
    dir_rows = [r for r in rows if r.kind == "dir"]
    assert all(r.source_index == -1 for r in dir_rows)


def test_rename_uses_target_path():
    items = [(_file("old.txt -> src/new.txt"), 0)]
    rows = build_status_tree(items, set())
    assert _paths(rows) == [
        ("dir", "src", 0),
        ("file", "src/new.txt", 1),
    ]


def test_backslash_normalized():
    items = [(_file("src\\app\\main.py"), 0)]
    rows = build_status_tree(items, set())
    assert _paths(rows) == [
        ("dir", "src", 0),
        ("dir", "src/app", 1),
        ("file", "src/app/main.py", 2),
    ]


def test_child_indices_recursive():
    items = [
        (_file("src/a.py"), 0),
        (_file("src/deep/b.py"), 1),
        (_file("README.md"), 2),
    ]
    rows = build_status_tree(items, set())
    src_row = next(r for r in rows if r.kind == "dir" and r.path == "src")
    assert set(src_row.child_indices) == {0, 1}
    deep_row = next(r for r in rows if r.kind == "dir" and r.path == "src/deep")
    assert set(deep_row.child_indices) == {1}


def test_directory_sorted_before_files():
    items = [
        (_file("z.py"), 0),
        (_file("src/a.py"), 1),
        (_file("aaa.py"), 2),
    ]
    rows = build_status_tree(items, set())
    assert [r.path for r in rows] == ["src", "src/a.py", "aaa.py", "z.py"]


def test_summarize():
    files = [
        _file("a.py", short_status=" M"),  # modified
        _file("b.py", short_status="A ", has_staged=True, has_unstaged=False),  # staged
    ]
    assert _summarize(files) == "1 staged · 1 modified"


def test_summarize_empty():
    assert _summarize([]) == ""
