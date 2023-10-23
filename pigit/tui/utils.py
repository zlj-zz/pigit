import re
from functools import lru_cache
from typing import List, Tuple, Pattern


WIDTHS: List[Tuple[int, int]] = [
    (126, 1),
    (159, 0),
    (687, 1),
    (710, 0),
    (711, 1),
    (727, 0),
    (733, 1),
    (879, 0),
    (1154, 1),
    (1161, 0),
    (4347, 1),
    (4447, 2),
    (7467, 1),
    (7521, 0),
    (8369, 1),
    (8426, 0),
    (9000, 1),
    (9002, 2),
    (11021, 1),
    (12350, 2),
    (12351, 1),
    (12438, 2),
    (12442, 0),
    (19893, 2),
    (19967, 1),
    (55203, 2),
    (63743, 1),
    (64106, 2),
    (65039, 1),
    (65059, 0),
    (65131, 2),
    (65279, 1),
    (65376, 2),
    (65500, 1),
    (65510, 2),
    (120831, 1),
    (262141, 2),
    (1114109, 1),
]


@lru_cache(maxsize=1024)
def get_width(r: int) -> int:
    """Gets the width occupied by characters on the command line."""

    if r in {0xE, 0xF}:
        return 0
    return next((wid for num, wid in WIDTHS if r <= num), 1)


_STYLE_ANSI_RE: Pattern[str] = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m|\033\[\d+m")


def plain(text: str):
    """Remove color ansi code from text."""
    return _STYLE_ANSI_RE.sub("", text)
