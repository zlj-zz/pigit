from __future__ import annotations

import os
import textwrap

from .const import __url__, __version__
from .git import LocalGit, git_version


def introduce() -> str:
    """Print the description information."""

    # Print version.
    introduce_str = textwrap.dedent("""\
        @pink( ____ ___ ____ ___ _____
        |  _ \\ _/ ___|_ _|_   _|
        | |_) | | |  _ | |  | |
        |  __/| | |_| || |  | |
        |_|  |___\\____|___| |_|) version: {version}

        {git_version}

        @bold(Local path): @underline(@sky_blue({local_path}))

        @bold(Description:)
        Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.
        The open source path on github: @underline(@sky_blue({url}))

        You can use @green(-h) or @green(--help) to get help and usage.
        """)

    # Print git version.
    _git_version = git_version() or "@red(Don't found Git, maybe need install.)"

    return introduce_str.format(
        version=__version__,
        git_version=_git_version,
        local_path=os.path.dirname(__file__.replace("./", "")),
        url=__url__,
    )


def show_gitconfig(
    path: str | None = None,
    format_type: str = "normal",
    color: bool = True,
) -> str:
    """Return git config info with format.

    Args:
        path: Path to git repository. Defaults to None.
        format_type: Output format style. Defaults to "normal".
        color: Whether to apply color. Defaults to True.

    Returns:
        Formatted git config string.
    """
    repo_handle = LocalGit(path=path)
    repo_path, _ = repo_handle.confirm_repo()

    if not repo_path:
        return (
            "@red(This directory is not a git repository yet.)"
            if color
            else "This directory is not a git repository yet."
        )

    config = repo_handle.get_config()

    if not config:
        return (
            "@red(Error reading configuration file.)"
            if color
            else "Error reading configuration file."
        )

    gen = []

    for tit, kv in config.items():
        gen.append(f"@tomato([{tit}])" if color else f"[{tit}]")
        gen.extend(
            f"\t@sky_blue({k})=@violet_red({v})" if color else f"\t{k}={v}"
            for k, v in kv.items()
        )

    return "\n".join(gen)
