# -*- coding:utf-8 -*-
import sys
import re
from typing import Dict, Optional, Match, Callable

# For encoding.
Icon_Supported_Encoding: list = ["utf-8"]

_ReStringMatch = Match[str]  # regex match object
_ReSubCallable = Callable[[_ReStringMatch], str]  # Callable invoked by re.sub
_EmojiSubMethod = Callable[[_ReSubCallable, str], str]  # Sub method of a compiled re
# https://github.com/willmcgugan/rich/blob/master/rich/_emoji_replace.py

_EMOJI_RE: _ReStringMatch = re.compile(
    r"(:(\S*?)(?:(?:\-)(emoji|text))?:)", re.M | re.S
)  # allow multi lines.


class Emoji(object):
    _EMOTION: Dict[str, str] = {
        "rainbow": "🌈",
        "smiler": "😊",
        "thinking": "🧐",
        "sorry": "😅",
    }

    _WIN_EMOTION: Dict[str, str] = {
        "rainbow": "::",
        "smiler": "^_^",
        "thinking": "-?-",
        "sorry": "Orz",
    }

    EMOTION: Dict[str, str]

    # XXX(zachary): There are some problems with the output emoji on windows.
    # ? In CMD, encoding is right, but emoji is error.
    # ? In git bash, encoding is not right, but seem can't detection.
    if (
        not sys.platform.lower().startswith("win")
        and sys.getdefaultencoding().lower() in Icon_Supported_Encoding
    ):
        EMOTION = _EMOTION
    else:
        EMOTION = _WIN_EMOTION

    __locals = locals()
    for k, v in EMOTION.items():
        __locals[k] = v

    # Try to render the emoji from str. If the emoji code is invalid  will
    # keep raw.
    #
    #           +----------------------> content
    #           |               +------> emoji code
    #           |               |
    #   today is a nice day :rainbow:
    @classmethod
    def render_emoji(
        cls,
        _msg: str,
        /,
        *,
        default_variant: Optional[str] = None,
        _emoji_sub: _EmojiSubMethod = _EMOJI_RE.sub,
    ):
        get_emoji = cls.EMOTION.__getitem__
        variants = {"text": "\uFE0E", "emoji": "\uFE0F"}
        get_variant = variants.get
        default_variant_code = (
            variants.get(default_variant, "") if default_variant else ""
        )

        def do_replace(match: Match[str]) -> str:
            emoji_code, emoji_name, variant = match.groups()
            try:
                return get_emoji(emoji_name.lower()) + get_variant(
                    variant, default_variant_code
                )
            except KeyError:
                return emoji_code

        return _emoji_sub(do_replace, _msg)


if __name__ == "__main__":
    print(Emoji.render_emoji("Today is a nice day :smiler:."))
