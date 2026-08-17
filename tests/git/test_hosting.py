# -*- coding: utf-8 -*-
"""
Module: tests/git/test_hosting.py
Description: Tests for create-PR URL building from git remotes.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

import pytest

from pigit.git.hosting import (
    RemoteParseError,
    UnsupportedHostingError,
    build_create_pr_url,
    normalize_remote_to_https,
)


class TestNormalizeRemote:
    def test_https_strips_git_suffix(self):
        assert (
            normalize_remote_to_https("https://github.com/zlj-zz/pigit.git")
            == "https://github.com/zlj-zz/pigit"
        )

    def test_ssh_scp_form(self):
        assert (
            normalize_remote_to_https("git@github.com:zlj-zz/pigit.git")
            == "https://github.com/zlj-zz/pigit"
        )

    def test_ssh_url_form(self):
        assert (
            normalize_remote_to_https("ssh://git@gitlab.com/group/proj.git")
            == "https://gitlab.com/group/proj"
        )

    def test_invalid_returns_none(self):
        assert normalize_remote_to_https("not-a-remote") is None


class TestBuildCreatePrUrl:
    def test_github_default(self):
        url = build_create_pr_url(
            remote_url="git@github.com:zlj-zz/pigit.git",
            head_branch="dev",
        )
        assert url == "https://github.com/zlj-zz/pigit/compare/dev?expand=1"

    def test_github_encodes_slash_in_branch(self):
        url = build_create_pr_url(
            remote_url="https://github.com/zlj-zz/pigit.git",
            head_branch="feat/x",
        )
        assert url == "https://github.com/zlj-zz/pigit/compare/feat%2Fx?expand=1"

    def test_github_with_base(self):
        url = build_create_pr_url(
            remote_url="https://github.com/zlj-zz/pigit.git",
            head_branch="dev",
            base_branch="main",
        )
        assert url == "https://github.com/zlj-zz/pigit/compare/main...dev?expand=1"

    def test_gitlab(self):
        url = build_create_pr_url(
            remote_url="git@gitlab.com:acme/app.git",
            head_branch="feat/x",
        )
        assert (
            url
            == "https://gitlab.com/acme/app/-/merge_requests/new"
            "?merge_request%5Bsource_branch%5D=feat%2Fx"
        )

    def test_bitbucket(self):
        url = build_create_pr_url(
            remote_url="https://bitbucket.org/acme/app.git",
            head_branch="dev",
        )
        assert (
            url
            == "https://bitbucket.org/acme/app/pull-requests/new?source=dev&t=1"
        )

    def test_gitea(self):
        url = build_create_pr_url(
            remote_url="https://try.gitea.io/acme/app.git",
            head_branch="dev",
        )
        assert url == "https://try.gitea.io/acme/app/compare/dev"

    def test_codeberg(self):
        url = build_create_pr_url(
            remote_url="git@codeberg.org:acme/app.git",
            head_branch="dev",
        )
        assert url == "https://codeberg.org/acme/app/compare/dev"

    def test_unsupported_host(self):
        with pytest.raises(UnsupportedHostingError):
            build_create_pr_url(
                remote_url="https://example.com/acme/app.git",
                head_branch="dev",
            )

    def test_unparseable_remote(self):
        with pytest.raises(RemoteParseError):
            build_create_pr_url(remote_url="bogus", head_branch="dev")


class TestHeadBranchForPr:
    def test_local_unchanged(self):
        from pigit.git.hosting import head_branch_for_pr

        assert head_branch_for_pr(name="dev", is_remote=False) == "dev"

    def test_remote_strips_remote_name(self):
        from pigit.git.hosting import head_branch_for_pr

        assert head_branch_for_pr(name="origin/dev", is_remote=True) == "dev"
        assert (
            head_branch_for_pr(name="origin/feat/x", is_remote=True) == "feat/x"
        )
