from typing import Dict, Literal, Optional, Tuple
import os, re

from plenty.table import UintTable
from plenty import box

from .const import __version__, __url__
from .gitlib.options import GitOption


git = GitOption()


def introduce() -> str:
    """Print the description information."""

    # Print version.
    introduce_str = """\
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

    # Print git version.
    git_version = git.git_version or "`Don't found Git, maybe need install.`<error>"

    return introduce_str.format(
        version=__version__,
        git_version=git_version,
        local_path=os.path.dirname(__file__.replace("./", "")),
        url=__url__,
    )


# ============
# Config info
# ============
FormatType = Literal["normal", "table"]


class GitConfig:
    def __init__(
        self,
        repo_path: Optional[str] = None,
        format_type: FormatType = "table",
        color: bool = True,
    ) -> None:
        self.repo_path = repo_path or "."
        self.format_type = format_type
        self.color = color

    @property
    def repo_info(self) -> Tuple[str, str]:
        return git.get_repo_info(self.repo_path)

    def parse_git_config(self, config_context: str) -> Dict:
        """Retrun a dict from parsing git local config.

        Args:
            conf (str): git local config string.

        Returns:
            dict: git local config dict.
        """
        conf_list = re.split(r"\r\n|\r|\n", config_context)
        config_dict: dict[str, dict[str, str]] = {}
        config_type: str = ""

        for line in conf_list:
            line = line.strip()

            if not line:
                continue

            elif line.startswith("["):
                config_type = line[1:-1].strip()
                config_dict[config_type] = {}

            elif "=" in line:
                key, value = line.split("=", 1)
                config_dict[config_type][key.strip()] = value.strip()

            else:
                continue

        return config_dict

    def normal_config(self, config_dict: Dict[str, Dict]) -> str:
        gen = []
        color = self.color

        for tit, kv in config_dict.items():
            gen.append(f"`[{tit}]`<tomato>" if color else f"[{tit}]")
            gen.extend(
                f"\t`{k}`<sky_blue>=`{v}`<medium_violet_red>" if color else f"\t{k}={v}"
                for k, v in kv.items()
            )

        return "\n".join(gen)

    def table_config(self, config_dict: Dict[str, Dict]) -> str:
        style = ["", "pale_green" if self.color else ""]
        tb = UintTable(title="Git Local Config", box=box.DOUBLE_EDGE)

        for header, values in config_dict.items():
            tb.add_unit(header, header_style="bold", values=values, values_style=style)

        return tb

    def generate(self) -> str:
        repo_path, config_path = self.repo_info

        if not repo_path:
            return (
                "`This directory is not a git repository yet.`<error>"
                if self.color
                else "This directory is not a git repository yet."
            )

        try:
            with open(f"{config_path}/config", "r") as cf:
                context = cf.read()
        except Exception as e:
            return (
                f"`Error reading configuration file; {e}.`<error>"
                if self.color
                else f"Error reading configuration file; {e}."
            )
        else:
            config_dict = self.parse_git_config(context)
            ft = self.format_type

            if ft == "table":
                return self.table_config(config_dict)
            else:
                # Unrecognized types and normal are considered normal.
                return self.normal_config(config_dict)
