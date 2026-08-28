"""
Module: tests/app/test_app_keybindings.py
Description: Tests for pigit.app_keybindings (enumerate + render keybinding template).
Author: Zev
Date: 2026-08-16
"""

from __future__ import annotations

import ast
from pathlib import Path

from pigit.app_keybindings import (
    _KEYMAP_CLASSES,
    _toml_str,
    collect_all_action_bindings,
    render_keybindings_template,
    warn_unmatched_keybindings,
)
from pigit.termui import Binding


def _binding(action: str, *keys: str, desc=None, configurable: bool = True) -> Binding:
    return Binding(
        action=action, keys=keys, target=action, desc=desc, configurable=configurable
    )


class TestCollectAllActionBindings:
    def test_enumerates_namespaces(self):
        bindings = collect_all_action_bindings()
        namespaces = {ns for ns, _ in bindings}
        assert namespaces == {
            "universal",
            "status",
            "diff",
            "rebase",
            "branch",
            "commit",
            "stash",
            "recent",
            "repo_switcher",
            "worktree_picker",
            "bisect",
            "log_ref",
            "inspector",
            "welcome",
        }

    def test_ast_scan_finds_no_unregistered_keymaps(self):
        # Reverse guard: every keymap_namespace declared in app modules must be
        # registered in _KEYMAP_CLASSES (runtime __subclasses__ misses lazily
        # imported panels, so scan statically instead).
        registered = {cls.keymap_namespace for cls in _KEYMAP_CLASSES}
        declared: set[str] = set()
        root = Path(__file__).resolve().parents[2] / "pigit"
        for path in sorted(root.glob("app*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "keymap_namespace":
                        value = node.value
                        if isinstance(value, ast.Constant) and isinstance(
                            value.value, str
                        ):
                            declared.add(value.value)
        assert declared <= registered


class TestRenderKeybindingsTemplate:
    def test_overridden_action_is_active_with_default(self):
        bindings = [
            ("branch", _binding("branch.checkout", "c", desc="Checkout branch"))
        ]
        out = render_keybindings_template(bindings, {"branch.checkout": "C"})
        assert 'checkout = "C"' in out
        assert '# default: "c"' in out

    def test_default_uses_binding_keys_not_override(self):
        bindings = [("branch", _binding("branch.checkout", "c", desc="Checkout"))]
        out = render_keybindings_template(bindings, {"branch.checkout": "C"})
        assert '# default: "c"' in out
        assert '# default: "C"' not in out

    def test_non_overridden_included_only_with_defaults(self):
        bindings = [
            ("branch", _binding("branch.checkout", "c", desc="Checkout branch"))
        ]
        assert "checkout" in render_keybindings_template(
            bindings, {}, include_defaults=True
        )
        assert render_keybindings_template(bindings, {}, include_defaults=False) == ""

    def test_configurable_false_skipped(self):
        bindings = [("branch", _binding("branch.locked", "x", configurable=False))]
        assert render_keybindings_template(bindings, {}, include_defaults=True) == ""
        assert render_keybindings_template(bindings, {"branch.locked": "y"}) == ""

    def test_desc_none_omits_comment(self):
        bindings = [("branch", _binding("branch.act", "a"))]
        out = render_keybindings_template(bindings, {}, include_defaults=True)
        assert '# act = "a"' in out
        assert '# act = "a"  #' not in out

    def test_callable_desc_falls_back_to_short_action(self):
        bindings = [("branch", _binding("branch.act", "a", desc=lambda self: "x"))]
        out = render_keybindings_template(bindings, {}, include_defaults=True)
        assert '# act = "a"  # act' in out

    def test_namespace_header_and_short_action_name(self):
        bindings = [
            ("branch", _binding("branch.checkout", "c", desc="Checkout branch"))
        ]
        out = render_keybindings_template(bindings, {}, include_defaults=True)
        assert "[keybindings.branch]" not in out
        assert "[app.keybindings.branch]" in out
        # short name only inside the nested table, not the dotted full id
        assert "# checkout =" in out
        assert "branch.checkout =" not in out


class TestTomlStr:
    def test_single_key_collapses_to_scalar(self):
        assert _toml_str(("c",)) == '"c"'
        assert _toml_str("c") == '"c"'

    def test_multi_key_array(self):
        assert _toml_str(("j", "down")) == '["j", "down"]'

    def test_space_key(self):
        assert _toml_str((" ",)) == '" "'

    def test_special_chars_escaped(self):
        # backslash and quote are valid printable keys; they must be escaped, not rejected
        assert _toml_str(("\\",)) == r'"\\"'
        assert _toml_str(('a"b',)) == r'"a\"b"'


class TestWarnUnmatched:
    def test_no_orphans_no_output(self, capsys):
        bindings = [("branch", _binding("branch.checkout", "c"))]
        warn_unmatched_keybindings(bindings, {"branch.checkout": "C"})
        assert capsys.readouterr().err == ""

    def test_orphan_warned(self, capsys):
        bindings = [("branch", _binding("branch.checkout", "c"))]
        warn_unmatched_keybindings(bindings, {"branch.checkoutt": "C"})
        assert "branch.checkoutt" in capsys.readouterr().err

    def test_non_configurable_override_warned(self, capsys):
        # render skips configurable=False, so such an override must be warned, not dropped silently
        bindings = [("branch", _binding("branch.locked", "x", configurable=False))]
        warn_unmatched_keybindings(bindings, {"branch.locked": "X"})
        assert "branch.locked" in capsys.readouterr().err
