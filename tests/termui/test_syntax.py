# -*- coding: utf-8 -*-
"""Tests for the syntax tokenizer."""

from __future__ import annotations

import pytest

from pigit.termui._syntax import (
    SyntaxTokenizer,
    SYNTAX_COLORS,
)
from pigit.app_theme import THEME


class TestDetectLanguage:
    def test_python(self):
        t = SyntaxTokenizer()
        assert t.detect_language("foo.py") == "py"
        assert t.detect_language("/path/to/bar.py") == "py"

    def test_javascript(self):
        t = SyntaxTokenizer()
        assert t.detect_language("app.js") == "js"
        assert t.detect_language("app.ts") == "ts"
        assert t.detect_language("app.jsx") == "jsx"
        assert t.detect_language("app.tsx") == "tsx"

    def test_go(self):
        t = SyntaxTokenizer()
        assert t.detect_language("main.go") == "go"

    def test_rust(self):
        t = SyntaxTokenizer()
        assert t.detect_language("lib.rs") == "rs"

    def test_generic_fallback(self):
        t = SyntaxTokenizer()
        assert t.detect_language("README") == "generic"
        assert t.detect_language("") == "generic"


class TestTokenizePython:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_keywords_control(self, tok):
        tokens = tok.tokenize("if x:", "py")
        assert tokens[0] == ("if", "keyword_control")

    def test_keywords_decl(self, tok):
        tokens = tok.tokenize("def foo():", "py")
        assert tokens[0] == ("def", "keyword_decl")

    def test_keywords_type(self, tok):
        tokens = tok.tokenize("x = True", "py")
        types = {t for _, t in tokens}
        assert "keyword_type" in types

    def test_builtins(self, tok):
        tokens = tok.tokenize("print(x)", "py")
        assert tokens[0] == ("print", "builtin")

    def test_string_double_quote(self, tok):
        tokens = tok.tokenize('x = "hello"', "py")
        types = [t for _, t in tokens]
        assert "string" in types

    def test_string_single_quote(self, tok):
        tokens = tok.tokenize("x = 'hello'", "py")
        types = [t for _, t in tokens]
        assert "string" in types

    def test_comment(self, tok):
        tokens = tok.tokenize("x = 1  # comment", "py")
        assert tokens[-1] == ("# comment", "comment")

    def test_number(self, tok):
        tokens = tok.tokenize("x = 42", "py")
        types = [t for _, t in tokens]
        assert "number" in types

    def test_function_call(self, tok):
        tokens = tok.tokenize("foo()", "py")
        assert tokens[0] == ("foo", "call")

    def test_merged_adjacent(self, tok):
        tokens = tok.tokenize("abc def", "py")
        # 'abc' and 'def' are both variable but separated by space
        # The space should be punct and break adjacency
        texts = [t for t, _ in tokens]
        assert "abc" in texts
        assert "def" in texts


class TestTokenizeJavaScript:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_control(self, tok):
        tokens = tok.tokenize("if (x) {", "js")
        assert tokens[0] == ("if", "keyword_control")

    def test_decl(self, tok):
        tokens = tok.tokenize("const x = 1;", "js")
        assert tokens[0] == ("const", "keyword_decl")

    def test_template_string(self, tok):
        tokens = tok.tokenize("x = `hello`;", "js")
        types = [t for _, t in tokens]
        assert "string" in types


class TestTokenizeGo:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_func(self, tok):
        tokens = tok.tokenize("func main() {", "go")
        assert tokens[0] == ("func", "keyword_decl")

    def test_builtin(self, tok):
        tokens = tok.tokenize("len(s)", "go")
        assert tokens[0] == ("len", "builtin")


class TestTokenizeRust:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_fn(self, tok):
        tokens = tok.tokenize("fn main() {", "rs")
        assert tokens[0] == ("fn", "keyword_decl")

    def test_unsafe_storage(self, tok):
        tokens = tok.tokenize("unsafe {", "rs")
        assert tokens[0] == ("unsafe", "keyword_storage")

    def test_lifetime(self, tok):
        tokens = tok.tokenize("x: &'a str", "rs")
        texts = [t for t, _ in tokens]
        assert "'a" in texts
        types = {t for _, t in tokens}
        assert "special" in types


class TestTokenizeDiffHunk:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_hunk_header(self, tok):
        tokens = tok.tokenize_diff_hunk("@@ -45,10 +46,15 @@")
        texts = [t for t, _ in tokens]
        assert "@@" in texts
        assert "45" in texts
        assert "10" in texts
        assert "46" in texts
        assert "15" in texts

    def test_hunk_no_match(self, tok):
        tokens = tok.tokenize_diff_hunk("@@ weird @@")
        assert tokens == [("@@ weird @@", "diff_meta")]


class TestTokenizeMarkdown:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_heading(self, tok):
        tokens = tok.tokenize_markdown("# Title")
        assert tokens[0] == ("#", "keyword")
        assert tokens[2] == ("Title", "keyword")

    def test_bold(self, tok):
        tokens = tok.tokenize_markdown("**bold**")
        assert ("**bold**", "keyword") in tokens

    def test_inline_code(self, tok):
        tokens = tok.tokenize_markdown("`code`")
        assert ("`code`", "string") in tokens

    def test_link(self, tok):
        tokens = tok.tokenize_markdown("[text](url)")
        assert ("[", "punct") in tokens
        assert ("text", "diff_meta") in tokens
        assert ("url", "comment") in tokens


class TestResolveColor:
    def test_global_keyword_control(self):
        assert SyntaxTokenizer.resolve_color("keyword_control", "py") == SYNTAX_COLORS["keyword_control"]

    def test_rust_override(self):
        # Rust overrides keyword_storage to accent_red
        assert SyntaxTokenizer.resolve_color("keyword_storage", "rs") == THEME.accent_red

    def test_fallback(self):
        assert SyntaxTokenizer.resolve_color("unknown_type", "py") == SYNTAX_COLORS["variable"]


class TestCache:
    def test_cache_hit(self):
        tok = SyntaxTokenizer()
        r1 = tok.tokenize("x = 1", "py")
        r2 = tok.tokenize("x = 1", "py")
        assert r1 is r2  # same cached object


class TestMultilineMask:
    @pytest.fixture
    def tok(self):
        return SyntaxTokenizer()

    def test_python_docstring_double_quote(self, tok):
        lines = [
            '+def foo():',
            '+    """This is a docstring',
            '+    that spans multiple',
            '+    lines."""',
            '+    pass',
        ]
        mask = tok.compute_multiline_mask(lines, "py")
        assert mask == [None, "docstring", "docstring", "docstring", None]

    def test_python_docstring_single_quote(self, tok):
        lines = [
            "+    '''Start",
            "+    middle",
            "+    end'''",
        ]
        mask = tok.compute_multiline_mask(lines, "py")
        assert mask == ["docstring", "docstring", "docstring"]

    def test_python_single_line_docstring_ignored(self, tok):
        """Single-line docstrings are handled by the regex; mask should be None."""
        lines = ['+    """A single line docstring."""']
        mask = tok.compute_multiline_mask(lines, "py")
        assert mask == [None]

    def test_c_block_comment(self, tok):
        lines = [
            "+int main() {",
            "+    /* This is a",
            "+       multi-line comment */",
            "+    return 0;",
        ]
        mask = tok.compute_multiline_mask(lines, "c")
        assert mask == [None, "comment", "comment", None]

    def test_hunk_header_resets_state(self, tok):
        lines = [
            '+    """Docstring part 1',
            "@@ -10,5 +12,7 @@",
            '+    part 2"""',
        ]
        mask = tok.compute_multiline_mask(lines, "py")
        assert mask == ["docstring", None, None]

    def test_alias_language_uses_base_config(self, tok):
        """ts aliases js, but compute_multiline_mask should still work via base_lang resolution."""
        lines = [
            "+    /* block",
            "+       comment */",
        ]
        mask = tok.compute_multiline_mask(lines, "ts")
        assert mask == ["comment", "comment"]

    def test_no_newline_line_skipped(self, tok):
        lines = [
            '+    """Docstring',
            "\\ No newline at end of file",
            '+    end."""',
        ]
        mask = tok.compute_multiline_mask(lines, "py")
        assert mask == ["docstring", None, "docstring"]
