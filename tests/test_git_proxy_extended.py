# -*- coding: utf-8 -*-
"""Extra :class:`~pigit.git.proxy.GitProxy` coverage for process/help/do paths."""

from unittest.mock import MagicMock, patch

import pytest

from pigit.git.define import GitCommandType
from pigit.git.proxy import PROMPT_WITH_SAME_OUT, PROMPT_WITH_TIPS, GitProxy


def test_process_unknown_command():
    g = GitProxy(extra_cmds={})
    code, msg = g.process_command("nope", None)
    assert code == 1 and "Don't support" in msg


def test_process_empty_command_option():
    g = GitProxy(extra_cmds={"x": {"help": "h"}})
    code, msg = g.process_command("x", None)
    assert code == 2


def test_process_discards_args_when_not_allowed():
    g = GitProxy(
        extra_cmds={"x": {"command": "git status", "has_arguments": False}},
        display=False,
    )
    ex = MagicMock()
    g.executor = ex
    code, msg = g.process_command("x", ["a", "b"])
    assert code == 0
    ex.exec.assert_called_once()
    assert "Discard" in msg or "parameters" in msg


def test_process_callable_command():
    def _fn(args):
        return f"ok:{args}"

    g = GitProxy(extra_cmds={"z": {"command": _fn, "has_arguments": True}})
    code, msg = g.process_command("z", ["1"])
    assert code == 0 and "ok:" in msg


def test_process_callable_raises():
    def _bad(_):
        raise RuntimeError("boom")

    g = GitProxy(extra_cmds={"z": {"command": _bad}})
    code, msg = g.process_command("z", None)
    assert code == 3 and "boom" in msg


def test_process_string_with_display():
    g = GitProxy(
        extra_cmds={"w": {"command": "git status", "has_arguments": True}},
        display=True,
    )
    g.executor = MagicMock()
    code, msg = g.process_command("w", ["-s"])
    assert code == 0
    assert "rainbow" in msg


def test_process_unsupported_command_type():
    g = GitProxy(extra_cmds={"q": {"command": 123}})
    code, msg = g.process_command("q", None)
    assert code == 5


def test_do_prompt_tips_confirm(monkeypatch):
    g = GitProxy(prompt=True, prompt_type=PROMPT_WITH_TIPS)
    with patch("pigit.git.proxy.similar_command", return_value="ws"):
        with patch("pigit.git.proxy.confirm", return_value=True):
            with patch.object(GitProxy, "process_command", side_effect=[(1, "x"), (0, "done")]) as pc:
                out = g.do("wx", None)
    assert out == "done"
    assert pc.call_count == 2


def test_do_prompt_same_out():
    g = GitProxy(
        prompt=True,
        prompt_type=PROMPT_WITH_SAME_OUT,
        extra_cmds={
            "ws": {"command": "git status", "help": "h"},
            "wss": {"command": "git status -s", "help": "h2"},
        },
    )
    msg = g.do("w", None)
    assert "maybe you want" in msg.lower() or "These are maybe" in msg


def test_generate_help_by_key_variants():
    g = GitProxy(
        extra_cmds={
            "a": {
                "help": "x " * 40,
                "command": "git a",
            },
            "b": {"command": lambda x: x},
        }
    )
    assert "a" in g.generate_help_by_key("a")
    assert "Func:" in g.generate_help_by_key("b") or "lambda" in g.generate_help_by_key("b")
    plain = g.generate_help_by_key("a", use_color=False)
    assert "a" in plain


def test_get_help_and_get_types():
    g = GitProxy(extra_cmds={"zz": {"command": "git zz", "help": "z"}})
    h = g.get_help()
    assert "zz" in h
    t = GitProxy.get_types()
    assert "`" in t


def test_get_help_by_type_valid():
    g = GitProxy()
    branch = GitCommandType.Branch.value
    out = g.get_help_by_type(branch.lower())
    assert branch in out or "orders" in out.lower()


def test_get_help_by_type_invalid_confirm():
    g = GitProxy(prompt=True)
    with patch("pigit.git.proxy.similar_command", return_value=GitCommandType.Branch.value):
        with patch("pigit.git.proxy.confirm", return_value=True):
            out = g.get_help_by_type("nope")
    assert "orders" in out.lower() or "Branch" in out


def test_get_help_by_type_invalid_reject():
    g = GitProxy(prompt=True)
    with patch("pigit.git.proxy.similar_command", return_value="Branch"):
        with patch("pigit.git.proxy.confirm", return_value=False):
            out = g.get_help_by_type("nope")
    assert "no such type" in out.lower() or "types" in out.lower()
