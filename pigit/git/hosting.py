# -*- coding: utf-8 -*-
"""
Module: pigit/git/hosting.py
Description: Build create-PR / merge-request browser URLs from git remotes.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from urllib.parse import quote, urlparse


class RemoteParseError(ValueError):
    """Raised when a git remote URL cannot be normalized to an HTTPS repo root."""


class UnsupportedHostingError(ValueError):
    """Raised when the remote host is not in the built-in provider table."""


# hostname -> provider id
_KNOWN_HOSTS: dict[str, str] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "try.gitea.io": "gitea",
    "gitea.com": "gitea",
    "codeberg.org": "codeberg",
}


def normalize_remote_to_https(remote_url: str) -> str | None:
    """
    Convert a git remote URL to ``https://host/owner/repo`` (no ``.git``).

    Supports HTTPS, ``git@host:path``, and ``ssh://`` forms.
    Returns None when the URL cannot be parsed.
    """
    raw = (remote_url or "").strip()
    if not raw:
        return None

    if raw.startswith("git@") and ":" in raw:
        # git@host:owner/repo.git
        _, rest = raw.split("@", 1)
        host, path = rest.split(":", 1)
        return _https_root(host, path)

    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https", "ssh") and parsed.netloc and parsed.path:
        host = parsed.hostname or parsed.netloc.split("@")[-1]
        return _https_root(host, parsed.path)

    return None


def _https_root(host: str, path: str) -> str | None:
    host = host.strip().lower()
    path = path.strip().lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.rstrip("/")
    if not host or not path or "/" not in path:
        return None
    return f"https://{host}/{path}"


def detect_provider(https_repo_root: str) -> str | None:
    """Return provider id for a normalized HTTPS repo root, or None."""
    host = (urlparse(https_repo_root).hostname or "").lower()
    return _KNOWN_HOSTS.get(host)


def build_create_pr_url(
    *,
    remote_url: str,
    head_branch: str,
    base_branch: str | None = None,
) -> str:
    """
    Build a browser URL that opens the create-PR / MR form for *head_branch*.

    Args:
        remote_url: Raw git remote URL (SSH or HTTPS).
        head_branch: Source branch name (already without remote prefix).
        base_branch: Optional target branch; only used for GitHub in v1 helpers.

    Returns:
        Absolute HTTPS URL for the hosting provider.

    Raises:
        RemoteParseError: Remote URL cannot be parsed.
        UnsupportedHostingError: Host is not in the built-in table.
        ValueError: Empty head branch.
    """
    head = (head_branch or "").strip()
    if not head:
        raise ValueError("head_branch must be non-empty")

    root = normalize_remote_to_https(remote_url)
    if root is None:
        raise RemoteParseError(f"Cannot parse remote URL: {remote_url!r}")

    provider = detect_provider(root)
    if provider is None:
        host = urlparse(root).hostname or "unknown"
        raise UnsupportedHostingError(f"Unsupported git host: {host}")

    enc_head = quote(head, safe="")
    base = (base_branch or "").strip()
    enc_base = quote(base, safe="") if base else ""

    if provider == "github":
        if enc_base:
            return f"{root}/compare/{enc_base}...{enc_head}?expand=1"
        return f"{root}/compare/{enc_head}?expand=1"

    if provider == "gitlab":
        url = (
            f"{root}/-/merge_requests/new"
            f"?merge_request%5Bsource_branch%5D={enc_head}"
        )
        if enc_base:
            url += f"&merge_request%5Btarget_branch%5D={enc_base}"
        return url

    if provider == "bitbucket":
        url = f"{root}/pull-requests/new?source={enc_head}&t=1"
        if enc_base:
            url += f"&dest={enc_base}"
        return url

    # gitea / codeberg
    if enc_base:
        return f"{root}/compare/{enc_base}...{enc_head}"
    return f"{root}/compare/{enc_head}"


def head_branch_for_pr(*, name: str, is_remote: bool) -> str:
    """
    Normalize a BranchPanel row name to a PR source branch.

    Remote-tracking names like ``origin/dev`` become ``dev``.
    """
    name = (name or "").strip()
    if is_remote and "/" in name:
        return name.split("/", 1)[1]
    return name
