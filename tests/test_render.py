from typing import Optional
import pytest
from .utils import analyze_it

from pigit.render.style import Style


@pytest.mark.parametrize(
    "text",
    [
        "Today is a b`nice` `day`<green,red>.",
        "Today is a b`nice`<#FF0000> day.",
        "Today is a `nice`<sky_blue> day.",
        "Today is a `nice`<,sky_blue> day.",
        "Today is a `nice`<> day.",
        "Today is a b```nice``` day.",
        "Today is a `nice`xxxxxxx day.",
        "Today is a `nice`<xxxxxxx> day.",
        "i`Don't found Git, maybe need install.`tomato",
    ],
)
def test_style_render_style(text: str):
    print("\n", Style.render_style(text))


@pytest.mark.parametrize(
    ["color", "bg_color", "bold", "dark", "italic", "underline", "blink", "strick"],
    [
        ["green", "", None, None, None, None, None, None],
        ["#ff0000", "green", None, None, None, None, None, None],
        ["", "yellow", None, None, None, None, None, None],
        ["sky_blue", "", True, False, None, None, None, None],
        ["sky_blue", "", None, True, None, None, None, None],
        ["sky_blue", "", None, None, True, None, None, None],
        ["sky_blue", "", None, None, None, True, None, None],
        ["sky_blue", "", None, None, None, None, True, None],
        ["sky_blue", "", None, None, None, None, None, True],
        ["sky_blue", "", True, None, True, True, True, True],
    ],
)
def test_style_render(color, bg_color, bold, dark, italic, underline, blink, strick):
    style = Style(
        color=color,
        bg_color=bg_color,
        bold=bold,
        dark=dark,
        italic=italic,
        underline=underline,
        blink=blink,
        strick=strick,
    )
    style.test()


# def test_style():
#     style = Style(color="green", bold=True)
#     print("\n", style)
#     style._make_ansi_code()
#     style.test()
