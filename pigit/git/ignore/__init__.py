from typing import Optional, Tuple
from shutil import get_terminal_size
from pathlib import Path

from .template import IGNORE_TEMPLATE


__all__ = ("get_ignore_source", "create_gitignore")


def get_ignore_source(t: str) -> Optional[str]:
    """Get gitignore source follow type."""

    return IGNORE_TEMPLATE.get(t)


def create_gitignore(
    t: str,
    file_name: str = ".gitignore",
    dir_path: Optional[str] = None,
    writing: bool = True,
) -> Tuple[int, str]:
    """Try to create a gitignore file.

    Args:
        t (str): project type.
        file_name (str, optional): file name. Defaults to ".gitignore".
        dir_path (Optional[str], optional): dir path. Defaults to None.
        writing (bool, optional): whether writing. Defaults to True.

    Returns:
        Tuple[int, str]: (code, message)
            code:
                0: successful
                1: don't write
                2: not supported
    """

    source = IGNORE_TEMPLATE.get(t.lower())
    path = Path(dir_path or ".").joinpath(file_name)

    if source is None:

        return 2, (
            f"Unsupported type: {t}\n"
            f'Supported type: [{" ".join(IGNORE_TEMPLATE)}]. Case insensitive.'
        )

    if not (writing and path.parent.is_dir()):
        width, _ = get_terminal_size()
        return 1, "{sep}{source}{sep}".format(sep="=" * width, source=source)

    with path.open(mode="w+") as f:
        f.write(source)

    return 0, f"Write gitignore file successful. Path: {path}"
