"""
Module: pigit/git/api/__init__.py
Description: GitApi facade over the domain git submodules.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import logging

from pigit.ext.executor import Executor
from pigit.ext.executor_factory import ExecutorFactory, ExecutorStrategy

from ._errors import GitError, RepoError
from ._core import _CoreOps
from ._branch import _BranchOps
from ._commit import _CommitOps, _DEFAULT_LOG_FORMAT, LOG_GRAPH_LIMIT
from ._status import _StatusOps
from ._stash import _StashOps
from ._diff import _DiffOps
from ._worktree import _WorktreeOps
from ._worktrees import WorktreeInfo, _WorktreesOps
from ._bisect import BisectState, _BisectOps
from ._merge import _MergeOps
from ._fileio import _FileioOps
from ._display import _DisplayOps

__all__ = ("GitApi", "GitError", "RepoError", "WorktreeInfo", "BisectState")


class GitApi:
    """Single working-copy git operations (optional default `path`).

    Facade over domain submodules, preserving the original method interface.
    """

    def __init__(
        self,
        executor: Executor | ExecutorStrategy | None = None,
        path: str | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.executor = executor or ExecutorFactory.get()
        self.log = log or logging.getLogger(__name__)
        self.path = path
        self._core = _CoreOps(self)
        self._branch = _BranchOps(self)
        self._commit = _CommitOps(self, self._core)
        self._status = _StatusOps(self, self._core)
        self._stash = _StashOps(self)
        self._diff = _DiffOps(self)
        self._worktree = _WorktreeOps(self, self._core)
        self._wt_ops = _WorktreesOps(self)
        self._bisect_ops = _BisectOps(self, self._core)
        self._merge = _MergeOps(self, self._core)
        self._fileio = _FileioOps(self)
        self._display = _DisplayOps(self, self._core, self._branch)

    def bind_path(self, path: str) -> "GitApi":
        """Return a new GitApi instance pinned to the given path."""
        return GitApi(executor=self.executor, path=path, log=self.log)

    # ── _core ──
    def confirm_repo(self, given_path=None, exclude_submodule=False):
        return self._core.confirm_repo(given_path, exclude_submodule)

    def get_config(self, path=None):
        return self._core.get_config(path)

    def get_config_value(self, key, path=None):
        return self._core.get_config_value(key, path)

    def get_head(self, path=None):
        return self._core.get_head(path)

    def get_current_branch(self, path=None):
        return self._core.get_current_branch(path)

    def has_upstream(self, path=None):
        return self._core.has_upstream(path)

    def default_push_remote(self, path=None):
        return self._core.default_push_remote(path)

    def get_first_pushed_commit(self, path=None, branch_name=None):
        return self._core.get_first_pushed_commit(path, branch_name)

    def get_remotes(self, path=None):
        return self._core.get_remotes(path)

    def get_remote_url(self, path=None, remote_name=None):
        return self._core.get_remote_url(path, remote_name)

    def _find_dot_git_dir(self, cwd):
        return self._core._find_dot_git_dir(cwd)

    def get_git_dir(self, path=None):
        return self._core.get_git_dir(path)

    def get_git_common_dir(self, path=None):
        return self._core.get_git_common_dir(path)

    def get_head_tracking(self, path=None):
        return self._core.get_head_tracking(path)

    def verify_commitish(self, ref, path=None):
        return self._core.verify_commitish(ref, path)

    # ── _branch ──
    def get_branches(self, path=None, include_remote=False, plain=True):
        return self._branch.get_branches(path, include_remote, plain)

    def load_branches(self, path=None, *, scope="local"):
        return self._branch.load_branches(path, scope=scope)

    def checkout_branch(self, branch_name, path=None):
        return self._branch.checkout_branch(branch_name, path)

    def rename_branch(self, old_name, new_name, path=None):
        return self._branch.rename_branch(old_name, new_name, path)

    def create_branch(self, branch_name, path=None):
        return self._branch.create_branch(branch_name, path)

    def delete_branch(self, branch_name, force=False, path=None):
        return self._branch.delete_branch(branch_name, force, path)

    def create_branch_at(self, branch_name, sha, path=None):
        return self._branch.create_branch_at(branch_name, sha, path)

    def _branch_sha(self, branch_name, path=None):
        return self._branch._branch_sha(branch_name, path)

    def get_branch_creation_time(self, branch_name, path=None):
        return self._branch.get_branch_creation_time(branch_name, path)

    def get_branch_recent_commit(self, branch_name, path=None):
        return self._branch.get_branch_recent_commit(branch_name, path)

    # ── _commit ──
    def load_log(
        self,
        branch_name="",
        limit=None,
        filter_path="",
        arg_str=_DEFAULT_LOG_FORMAT,
        path=None,
    ):
        return self._commit.load_log(branch_name, limit, filter_path, arg_str, path)

    def load_log_graph(self, branch_name, limit=LOG_GRAPH_LIMIT, path=None):
        return self._commit.load_log_graph(branch_name, limit, path)

    def iter_commits(
        self, branch_name, limit=True, max_commits=300, filter_path="", path=None
    ):
        return self._commit.iter_commits(
            branch_name, limit, max_commits, filter_path, path
        )

    def load_commits(
        self, branch_name, limit=True, filter_path="", path=None, max_commits=300
    ):
        return self._commit.load_commits(
            branch_name, limit, filter_path, path, max_commits
        )

    def get_commit_bodies(self, branch_name, max_commits=300, path=None):
        return self._commit.get_commit_bodies(branch_name, max_commits, path)

    def list_commits_in_range(self, base, path=None):
        return self._commit.list_commits_in_range(base, path)

    def load_commit_info(self, commit_sha="", file_name="", plain=False, path=None):
        return self._commit.load_commit_info(commit_sha, file_name, plain, path)

    def get_commit_stats(self, commit_sha, path=None):
        return self._commit.get_commit_stats(commit_sha, path)

    # ── _status ──
    def load_status(self, path=None, use_cache=True):
        return self._status.load_status(path, use_cache)

    def status_porcelain(self, path=None):
        return self._status.status_porcelain(path)

    def is_worktree_dirty(self, path=None):
        return self._status.is_worktree_dirty(path)

    def _load_status_cache_signature(self, cwd):
        return self._status._load_status_cache_signature(cwd)

    def has_staged_changes(self, path=None):
        return self._status.has_staged_changes(path)

    def has_unstaged_changes(self, path=None):
        return self._status.has_unstaged_changes(path)

    def has_untracked_changes(self, path=None):
        return self._status.has_untracked_changes(path)

    # ── _stash ──
    def load_stashes(self, path=None):
        return self._stash.load_stashes(path)

    def stash_push(self, path=None, message=""):
        return self._stash.stash_push(path, message)

    def stash_pop(self, ref, path=None):
        return self._stash.stash_pop(ref, path)

    def stash_apply(self, ref, path=None):
        return self._stash.stash_apply(ref, path)

    def stash_drop(self, ref, path=None):
        return self._stash.stash_drop(ref, path)

    def load_stash_diff(self, ref, path=None):
        return self._stash.load_stash_diff(ref, path)

    def stash_store(self, sha, path=None):
        return self._stash.stash_store(sha, path)

    def stash_numstat(self, ref, path=None):
        return self._stash.stash_numstat(ref, path)

    def stash_meta(self, ref, path=None):
        return self._stash.stash_meta(ref, path)

    # ── _diff ──
    def load_file_diff(self, file, tracked=True, cached=False, plain=False, path=None):
        return self._diff.load_file_diff(file, tracked, cached, plain, path)

    def get_file_history(self, path, repo_path=None):
        return self._diff.get_file_history(path, repo_path)

    def get_file_at_commit(self, commit_sha, path, repo_path=None, max_size=1_048_576):
        return self._diff.get_file_at_commit(commit_sha, path, repo_path, max_size)

    # ── _worktree ──
    def switch_file_status(self, file, path=None):
        return self._worktree.switch_file_status(file, path)

    def discard_file(self, file, path=None, tracked=None):
        return self._worktree.discard_file(file, path, tracked)

    def ignore_file(self, file, path=None):
        return self._worktree.ignore_file(file, path)

    def unignore_file(self, file, path=None):
        return self._worktree.unignore_file(file, path)

    def add_file(self, file, path=None):
        return self._worktree.add_file(file, path)

    def checkout_ours(self, file, path=None):
        return self._worktree.checkout_ours(file, path)

    def checkout_theirs(self, file, path=None):
        return self._worktree.checkout_theirs(file, path)

    def checkout_head_file(self, file, path=None):
        return self._worktree.checkout_head_file(file, path)

    def reset_head_file(self, file, path=None):
        return self._worktree.reset_head_file(file, path)

    def soft_reset_head1(self, path=None):
        return self._worktree.soft_reset_head1(path)

    # ── _wt_ops (git worktree feature; not working-tree file ops) ──
    def list_worktrees(self, path=None):
        return self._wt_ops.list_worktrees(path)

    def add_worktree(self, target, branch, *, new=True, path=None):
        return self._wt_ops.add_worktree(target, branch, new=new, path=path)

    def remove_worktree(self, target, *, force=False, path=None):
        return self._wt_ops.remove_worktree(target, force=force, path=path)

    def is_worktree(self, path=None):
        return self._wt_ops.is_worktree(path)

    # ── _bisect_ops ──
    def bisect_status(self, path=None):
        return self._bisect_ops.bisect_status(path)

    def bisect_start(self, good_ref, bad_ref=None, path=None):
        return self._bisect_ops.bisect_start(good_ref, bad_ref, path)

    def bisect_mark_good(self, path=None):
        return self._bisect_ops.bisect_mark_good(path)

    def bisect_mark_bad(self, path=None):
        return self._bisect_ops.bisect_mark_bad(path)

    def bisect_reset(self, path=None):
        return self._bisect_ops.bisect_reset(path)

    # ── _merge ──
    def pull(self, path=None):
        return self._merge.pull(path)

    def push(self, path=None):
        return self._merge.push(path)

    def push_set_upstream(self, remote, branch, path=None):
        return self._merge.push_set_upstream(remote, branch, path)

    def merge(self, source, path=None):
        return self._merge.merge(source, path)

    def is_merge_in_progress(self, path=None):
        return self._merge.is_merge_in_progress(path)

    def is_rebase_in_progress(self, path=None):
        return self._merge.is_rebase_in_progress(path)

    def sequencer_in_progress(self, path=None):
        return self._merge.sequencer_in_progress(path)

    def resolve_head_sha(self, path=None):
        return self._merge.resolve_head_sha(path)

    def is_ancestor(self, commit, of_ref="HEAD", path=None):
        return self._merge.is_ancestor(commit, of_ref, path)

    def has_unmerged_paths(self, path=None):
        return self._merge.has_unmerged_paths(path)

    def commit_no_edit(self, path=None):
        return self._merge.commit_no_edit(path)

    def amend_head(self, path=None):
        return self._merge.amend_head(path)

    def commit(self, message, path=None):
        return self._merge.commit(message, path)

    # ── _fileio ──
    def hash_object_file(self, file, path=None):
        return self._fileio.hash_object_file(file, path)

    def cat_file_to_path(self, sha, dest, path=None):
        return self._fileio.cat_file_to_path(sha, dest, path)

    def read_file_bytes(self, file, path=None):
        return self._fileio.read_file_bytes(file, path)

    def write_file_bytes(self, file, data, path=None):
        return self._fileio.write_file_bytes(file, data, path)

    def get_file_info(self, file, path=None):
        return self._fileio.get_file_info(file, path)

    def compare_index_worktree(self, relpath, path=None):
        return self._fileio.compare_index_worktree(relpath, path)

    def unmerged_stages(self, relpath, path=None):
        return self._fileio.unmerged_stages(relpath, path)

    def last_commit_for_path(self, relpath, path=None):
        return self._fileio.last_commit_for_path(relpath, path)

    def _format_size(self, size):
        return self._fileio._format_size(size)

    # ── _display ──
    def get_summary(self, path=None, plain=True):
        return self._display.get_summary(path, plain)

    def get_repo_desc(self, include_part=None, path=None, color=True):
        return self._display.get_repo_desc(include_part, path, color)
