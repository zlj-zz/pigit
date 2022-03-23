# -*- coding:utf-8 -*-
import doctest
from typing import Optional
import pytest
import doctest
from .utils import analyze_it

from pigit.render.console import Console
from pigit.render.style import Color, Style
from pigit.render.markup import render_markup
from pigit.render.table import Table, UintTable
from pigit.render import box
import pigit.render.str_utils
from pigit.render.str_utils import byte_str2str


class TestColor:
    @pytest.mark.parametrize(
        ["input_", "wanted"],
        [
            ["#FF0000", True],
            ["#FF0", False],
            ["#F0", True],
            [[255, 0, 0], True],
            [(255, 0, 0), True],
            [[-1, 0, 0], False],
            ["red", True],
            [None, False],
            [123456, False],
        ],
    )
    def test_is_color(self, input_, wanted):
        assert Color.is_color(input_) == wanted

    @pytest.mark.parametrize(
        "color",
        [
            None,
            "#FF0000",
            "#f0",
        ],
    )
    def test_instance(self, color):
        co = Color(color)
        print(co.hexa, co.rgb, repr(co.escape))
        print(co)


class TestStyle:
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
            "Today is a (bold,underline)`nice`<yellow> day.",
            "Today is a (bold ,  underline)`nice`<yellow> day.",
            "Today is a (bold,underline`nice`<yellow> day.",
            "Today is a bold,underline)`nice`<yellow> day.",
            "i`Don't found Git, maybe need install.`tomato",
        ],
    )
    def test_style_render_style(self, text: str):
        print("\n", Style.render_style(text))

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
    def test_style_remove_style(self, text: str):
        print("\n", Style.remove_style(text))

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
    def test_style_render(
        self, color, bg_color, bold, dark, italic, underline, blink, strick
    ):
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

    def test_style_add(self):
        style1 = Style(color="green", bold=True)
        style2 = Style(bg_color="red", bold=False, dark=True)

        print("\n", style1 + style2)

    @pytest.mark.parametrize(
        "text",
        [
            "Today is a b`nice` `day`<green,red>. bye.",
        ],
    )
    def test_style_render_markup(self, text: str):
        print("\n", text)
        render_markup(text)


class TestTableModule:
    def test_table(self):
        console = Console()
        # print(Text("`1234`<yellow>"))
        res_t = Table(
            title="Search Result",
            title_style="red",
            # box=box.SIMPLE_HEAD,
            caption="good table",
            caption_style="purple dark",
            border_style="red",
            show_edge=False,
            # show_lines=True
            # show_header=False
        )
        res_t.add_column("Idx", style="green")
        res_t.add_column("Fiction Name", style="yellow")
        res_t.add_column("Last Update", style="cyan")
        res_t.add_column("Other Info")

        res_t.add_row("12", "34", "56", "1")
        res_t.add_row("56", "`sun`<red> is so big.", "10.dark`00`", "1")
        res_t.add_row(
            "我最棒", "9", "25", "100, this is a length test, get large length text."
        )

        console.echo(res_t, "`sun`<red> is so big.")

    def test_unittable(self):
        ut = UintTable(
            title="unit table",
            box=box.DOUBLE_EDGE,
            border_style="sky_blue",
        )

        unit1 = ut.add_unit(
            "Fruit true color", header_style="red bold", values_style="yellow"
        )
        unit1.add_kv("apple", "red, this is a length test.\n second line.")
        unit1.add_kv("grape", "purple")

        unit1 = ut.add_unit("Animal color")
        unit1.add_kv("cattle", "yellow")
        unit1.add_kv(
            "sheep", "white, this is a length test, get large length text." * 10
        )

        console = Console()
        console.echo(ut)


class TestStrUtils:
    def test_str_utils(self):
        doctest.testmod(pigit.render.str_utils, verbose=True)

    def test_byte_str2str(self):
        s = byte_str2str(
            "test/\\346\\265\\213\\350\\257\\225\\344\\270\\255\\346\\226\\207.py"
        )
        print(s)
        assert s == "test/测试中文.py"
