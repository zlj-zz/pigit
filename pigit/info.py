import os
import textwrap
from typing import List, Literal, Optional, Union

from plenty import box
from plenty.table import UintTable
from plenty.style import Style

from .const import __url__, __version__
from .git import Repo, git_version


def introduce() -> str:
    """Print the description information."""

    # Print version.
    introduce_str = textwrap.dedent(
        """\
        ` ____ ___ ____ ___ _____
        |  _ \\_ _/ ___|_ _|_   _|
        | |_) | | |  _ | |  | |
        |  __/| | |_| || |  | |
        |_|  |___\\____|___| |_|`<pink> version: {version}

        {git_version}

        b`Local path`: u`{local_path}`<sky_blue>

        b`Description:`
        Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.
        The open source path on github: u`{url}`<sky_blue>

        You can use `-h`<ok> or `--help`<ok> to get help and usage.
        """
    )

    # Print git version.
    _git_version = git_version() or "`Don't found Git, maybe need install.`<error>"

    return introduce_str.format(
        version=__version__,
        git_version=_git_version,
        local_path=os.path.dirname(__file__.replace("./", "")),
        url=__url__,
    )


def show_gitconfig(
    path: Optional[str] = None,
    format_type: Literal["normal", "table"] = "table",
    color: bool = True,
) -> Union[str, UintTable]:
    """Return git config info with format.

    Args:
        path (Optional[str], optional): _description_. Defaults to None.
        format_type (Literal[&quot;normal&quot;, &quot;table&quot;], optional): _description_. Defaults to "table".
        color (bool, optional): _description_. Defaults to True.

    """
    repo_handle = Repo(path)
    repo_path, _ = repo_handle.confirm_repo()

    if not repo_path:
        return (
            "`This directory is not a git repository yet.`<error>"
            if color
            else "This directory is not a git repository yet."
        )

    config = repo_handle.get_config()

    if not config:
        return (
            "`Error reading configuration file.`<error>"
            if color
            else "Error reading configuration file."
        )

    if format_type == "table":
        style: List[Union[str, "Style"]] = ["", "pale_green" if color else ""]

        tb = UintTable(title="Git Local Config", box=box.DOUBLE_EDGE)
        for header, values in config.items():
            tb.add_unit(header, header_style="bold", values=values, values_style=style)

        return tb

    elif format_type == "normal":
        gen = []

        for tit, kv in config.items():
            gen.append(f"`[{tit}]`<tomato>" if color else f"[{tit}]")
            gen.extend(
                f"\t`{k}`<sky_blue>=`{v}`<medium_violet_red>" if color else f"\t{k}={v}"
                for k, v in kv.items()
            )

        return "\n".join(gen)

    else:
        return "Not support format style."
