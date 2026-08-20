# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_stat_mtime_backend.py
Description: Tests for StatMtimeBackend, FakeBackend, and metadata paths.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path

from pigit.observe.backend import FakeBackend, StatMtimeBackend
from pigit.observe.paths import build_git_metadata_paths
from pigit.observe.types import BackendHealth, PathSignal, WatchRoot


def test_stat_mtime_emits_when_file_changes(tmp_path: Path):
    target = tmp_path / "HEAD"
    target.write_text("ref: refs/heads/main\n")
    backend = StatMtimeBackend(paths=[str(target)])
    backend.start([])
    assert backend.poll() == []
    target.write_text("ref: refs/heads/other\n")
    signals = backend.poll()
    assert len(signals) == 1
    assert signals[0].path == str(target.resolve())


def test_stat_mtime_start_with_git_roots(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "refs" / "heads" / "main").write_text("abc\n")
    backend = StatMtimeBackend()
    backend.start(
        [
            WatchRoot(kind="git_dir", path=str(git_dir)),
            WatchRoot(kind="common_dir", path=str(git_dir)),
        ]
    )
    assert backend.poll() == []
    (git_dir / "HEAD").write_text("ref: refs/heads/other\n")
    signals = backend.poll()
    assert any(Path(s.path).name == "HEAD" for s in signals)


def test_fake_backend_returns_scripted_batches():
    s1 = PathSignal(path="/a", mtime_ns=1)
    s2 = PathSignal(path="/b", mtime_ns=2)
    backend = FakeBackend(scripted=[[s1], [s2]])
    backend.start([])
    assert backend.poll() == [s1]
    assert backend.poll() == [s2]
    assert backend.poll() == []
    assert backend.health() == BackendHealth.OK


def test_build_git_metadata_paths_skips_objects(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "index").write_bytes(b"")
    (git_dir / "objects" / "ab").mkdir(parents=True)
    (git_dir / "objects" / "ab" / "cd").write_bytes(b"x")
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "refs" / "heads" / "main").write_text("deadbeef\n")
    (git_dir / "logs").mkdir()
    (git_dir / "logs" / "HEAD").write_text("log\n")
    (git_dir / "logs" / "refs").mkdir(parents=True)

    paths = build_git_metadata_paths(str(git_dir), str(git_dir))
    joined = "\n".join(paths)
    assert "objects" not in joined
    assert any(p.endswith("HEAD") and "/logs/" not in p for p in paths)
    assert any(p.endswith("index") for p in paths)
    assert any(p.endswith("refs/heads/main") for p in paths)
    # Discovery dirs so newly created refs bump a watched mtime.
    assert (git_dir / "refs").resolve().as_posix() in {
        Path(p).resolve().as_posix() for p in paths
    }
    assert (git_dir / "refs" / "heads").resolve().as_posix() in {
        Path(p).resolve().as_posix() for p in paths
    }
    assert (git_dir / "logs" / "refs").resolve().as_posix() in {
        Path(p).resolve().as_posix() for p in paths
    }


def test_new_branch_ref_emits_via_heads_dir_then_tracks_file(tmp_path: Path):
    """Creating refs/heads/feature must signal; later tip edits must too."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    heads = git_dir / "refs" / "heads"
    heads.mkdir(parents=True)
    (heads / "main").write_text("aaa\n")

    backend = StatMtimeBackend()
    backend.start(
        [
            WatchRoot(kind="git_dir", path=str(git_dir)),
            WatchRoot(kind="common_dir", path=str(git_dir)),
        ]
    )
    assert backend.poll() == []

    (heads / "feature").write_text("bbb\n")
    first = backend.poll()
    assert first, "expected signal from refs/heads directory mtime"
    assert any(
        Path(s.path).resolve() in {heads.resolve(), (git_dir / "refs").resolve()}
        for s in first
    )

    (heads / "feature").write_text("ccc\n")
    second = backend.poll()
    assert any(Path(s.path).name == "feature" for s in second)
