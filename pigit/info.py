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
    color: bool = True,
) -> str:
    """Return git config info.

    Args:
        path: Path to git repository. Defaults to None.
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

    # Separate branch sections for potential folding.
    branch_sections: dict[str, dict[str, str]] = {}
    other_sections: dict[str, dict[str, str]] = {}
    for name, kv in config.items():
        if name.startswith('branch "'):
            branch_sections[name] = kv
        else:
            other_sections[name] = kv

    def _render_section(name: str, kv: dict[str, str]) -> list[str]:
        """Render one config section as aligned key=value lines."""
        lines: list[str] = []
        header = f"@bold(@red([{name}]))" if color else f"[{name}]"
        lines.append(header)
        if kv:
            max_key_len = max(len(k) for k in kv)
            for k, v in kv.items():
                padded = k.ljust(max_key_len)
                key_part = f"@green({padded})" if color else padded
                safe_v = v.replace("@", "@@")
                lines.append(f"  {key_part} = {safe_v}")
        return lines

    gen: list[str] = []

    # Render non-branch sections.
    for name, kv in other_sections.items():
        if gen:
            gen.append("")
        gen.extend(_render_section(name, kv))

    # Render branch sections.
    for name, kv in branch_sections.items():
        if gen:
            gen.append("")
        gen.extend(_render_section(name, kv))

    return "\n".join(gen)
