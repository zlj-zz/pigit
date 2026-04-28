# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_syntax.py
Description: Lightweight syntax tokenizer for diff code highlighting.
Author: Zev
Date: 2026-04-27
"""

from __future__ import annotations

import functools
import re
from typing import Optional

from .palette import (
    DEFAULT_FG,
    BLUE,
    CYAN,
    DIM,
    GREEN,
    MUTED,
    PURPLE,
    RED,
    YELLOW,
)

# ── Default syntax color mapping (uses palette constants) ──
# Callers can override via set_color_map() on SyntaxTokenizer.
_DEFAULT_COLORS: dict[str, tuple[int, int, int]] = {
    "keyword_control": PURPLE,
    "keyword_decl": BLUE,
    "keyword_storage": YELLOW,
    "keyword_type": CYAN,
    "keyword_operator": MUTED,
    "string": RED,
    "number": PURPLE,
    "comment": GREEN,
    "call": DEFAULT_FG,
    "builtin": CYAN,
    "type": CYAN,
    "variable": DEFAULT_FG,
    "operator": MUTED,
    "punct": DEFAULT_FG,
    "decorator": YELLOW,
    "special": RED,
    "docstring": RED,
    "diff_meta": BLUE,
    "diff_lineno": YELLOW,
    "diff_count": PURPLE,
}

# Public alias for backward compatibility and external callers.
SYNTAX_COLORS = _DEFAULT_COLORS


# ── Language configurations ──
_LANGUAGE_CONFIGS: dict[str, dict] = {
    # ── Python ──
    "py": {
        "keyword_categories": {
            "control": {
                "if",
                "elif",
                "else",
                "for",
                "while",
                "return",
                "break",
                "continue",
                "yield",
                "raise",
                "try",
                "except",
                "finally",
                "with",
                "async",
                "await",
                "pass",
            },
            "decl": {
                "def",
                "class",
                "import",
                "from",
                "as",
                "global",
                "nonlocal",
                "lambda",
                "assert",
                "del",
            },
            "storage": set(),
            "type": {
                "int",
                "str",
                "float",
                "bool",
                "list",
                "dict",
                "tuple",
                "set",
                "frozenset",
                "bytes",
                "bytearray",
                "memoryview",
                "object",
                "type",
                "None",
                "True",
                "False",
                "Ellipsis",
                "NotImplemented",
            },
            "operator": {"and", "or", "not", "in", "is"},
        },
        "builtins": {
            "abs",
            "all",
            "any",
            "ascii",
            "bin",
            "bool",
            "breakpoint",
            "bytearray",
            "bytes",
            "callable",
            "chr",
            "classmethod",
            "compile",
            "complex",
            "delattr",
            "dict",
            "dir",
            "divmod",
            "enumerate",
            "eval",
            "exec",
            "filter",
            "float",
            "format",
            "frozenset",
            "getattr",
            "globals",
            "hasattr",
            "hash",
            "help",
            "hex",
            "id",
            "input",
            "int",
            "isinstance",
            "issubclass",
            "iter",
            "len",
            "list",
            "locals",
            "map",
            "max",
            "memoryview",
            "min",
            "next",
            "object",
            "oct",
            "open",
            "ord",
            "pow",
            "print",
            "property",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "setattr",
            "slice",
            "sorted",
            "staticmethod",
            "str",
            "sum",
            "super",
            "tuple",
            "type",
            "vars",
            "zip",
            "__import__",
        },
        "comment": "#",
        "strings": {'"', "'"},
    },
    # ── JavaScript / TypeScript ──
    "js": {
        "keyword_categories": {
            "control": {
                "if",
                "else",
                "for",
                "while",
                "return",
                "break",
                "continue",
                "switch",
                "case",
                "default",
                "try",
                "catch",
                "finally",
                "throw",
                "yield",
                "await",
                "async",
                "do",
                "debugger",
            },
            "decl": {
                "function",
                "const",
                "let",
                "var",
                "class",
                "extends",
                "import",
                "from",
                "export",
                "default",
                "static",
                "get",
                "set",
                "of",
                "new",
                "this",
                "super",
                "with",
                "delete",
                "void",
                "typeof",
                "instanceof",
            },
            "storage": set(),
            "type": {
                "null",
                "undefined",
                "NaN",
                "Infinity",
                "true",
                "false",
            },
            "operator": {"in", "of", "as"},
        },
        "builtins": {
            "Array",
            "Boolean",
            "Date",
            "Error",
            "Function",
            "JSON",
            "Math",
            "Number",
            "Object",
            "Promise",
            "RegExp",
            "String",
            "Symbol",
            "console",
            "document",
            "window",
            "parseInt",
            "parseFloat",
            "isNaN",
            "isFinite",
            "decodeURI",
            "decodeURIComponent",
            "encodeURI",
            "encodeURIComponent",
        },
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "strings": {'"', "'", "`"},
    },
    "ts": {"_alias": "js"},
    "jsx": {"_alias": "js"},
    "tsx": {"_alias": "js"},
    # ── Go ──
    "go": {
        "keyword_categories": {
            "control": {
                "if",
                "else",
                "for",
                "range",
                "return",
                "break",
                "continue",
                "switch",
                "case",
                "default",
                "fallthrough",
                "goto",
            },
            "decl": {
                "func",
                "package",
                "import",
                "const",
                "var",
                "type",
                "struct",
                "interface",
                "map",
                "chan",
                "select",
                "go",
                "defer",
            },
            "storage": set(),
            "type": {
                "int",
                "int8",
                "int16",
                "int32",
                "int64",
                "uint",
                "uint8",
                "uint16",
                "uint32",
                "uint64",
                "uintptr",
                "float32",
                "float64",
                "complex64",
                "complex128",
                "bool",
                "byte",
                "rune",
                "string",
                "error",
                "nil",
                "true",
                "false",
            },
            "operator": set(),
        },
        "builtins": {
            "append",
            "cap",
            "close",
            "complex",
            "copy",
            "delete",
            "imag",
            "len",
            "make",
            "new",
            "panic",
            "print",
            "println",
            "real",
            "recover",
        },
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "strings": {'"', "`"},
    },
    # ── Rust ──
    "rs": {
        "keyword_categories": {
            "control": {
                "if",
                "else",
                "match",
                "for",
                "while",
                "loop",
                "return",
                "break",
                "continue",
                "await",
                "async",
            },
            "decl": {
                "fn",
                "pub",
                "use",
                "mod",
                "struct",
                "enum",
                "trait",
                "impl",
                "type",
                "crate",
                "extern",
                "dyn",
                "where",
                "let",
            },
            "storage": {"const", "static", "mut", "ref", "move", "unsafe"},
            "type": {"Self", "self", "true", "false"},
            "operator": {"as", "in", "where"},
        },
        "color_overrides": {
            "keyword_storage": RED,
        },
        "special_patterns": [(r"'[a-zA-Z_]\w*", "special")],
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "strings": {'"'},
    },
    # ── Java ──
    "java": {
        "keyword_categories": {
            "control": {
                "if",
                "else",
                "for",
                "while",
                "return",
                "break",
                "continue",
                "switch",
                "case",
                "default",
                "try",
                "catch",
                "finally",
                "throw",
                "do",
                "goto",
            },
            "decl": {
                "class",
                "interface",
                "enum",
                "extends",
                "implements",
                "import",
                "package",
                "new",
                "this",
                "super",
                "abstract",
                "native",
                "strictfp",
                "synchronized",
                "transient",
                "volatile",
                "throws",
                "instanceof",
            },
            "storage": {
                "public",
                "private",
                "protected",
                "static",
                "final",
                "const",
            },
            "type": {
                "boolean",
                "byte",
                "char",
                "short",
                "int",
                "long",
                "float",
                "double",
                "void",
                "null",
                "true",
                "false",
            },
            "operator": set(),
        },
        "builtins": {
            "String",
            "Object",
            "Integer",
            "Boolean",
            "Double",
            "Float",
            "Long",
            "Short",
            "Byte",
            "Character",
            "System",
            "Math",
            "Thread",
            "Exception",
            "Runtime",
            "Class",
        },
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "strings": {'"'},
    },
    "kt": {"_alias": "java"},
    # ── C / C++ ──
    "c": {
        "keyword_categories": {
            "control": {
                "if",
                "else",
                "for",
                "while",
                "return",
                "break",
                "continue",
                "switch",
                "case",
                "default",
                "do",
                "goto",
            },
            "decl": {
                "struct",
                "enum",
                "union",
                "typedef",
                "extern",
                "inline",
                "sizeof",
            },
            "storage": {
                "auto",
                "const",
                "register",
                "restrict",
                "static",
                "volatile",
                "signed",
                "unsigned",
            },
            "type": {
                "char",
                "short",
                "int",
                "long",
                "float",
                "double",
                "void",
                "bool",
                "true",
                "false",
                "NULL",
                "nullptr",
            },
            "operator": set(),
        },
        "preprocessor": True,
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "strings": {'"', "'"},
    },
    "cpp": {"_alias": "c"},
    "h": {"_alias": "c"},
    "hpp": {"_alias": "c"},
    # ── Shell ──
    "sh": {
        "keyword_categories": {
            "control": {
                "if",
                "then",
                "else",
                "elif",
                "fi",
                "for",
                "while",
                "do",
                "done",
                "case",
                "esac",
                "return",
                "select",
                "until",
                "in",
            },
            "decl": {
                "function",
                "export",
                "source",
                "local",
                "alias",
                "trap",
                "eval",
                "exec",
                "exit",
                "shift",
                "unset",
            },
            "storage": set(),
            "type": set(),
            "operator": set(),
        },
        "comment": "#",
        "strings": {'"', "'"},
        "variables": True,
    },
    "bash": {"_alias": "sh"},
    "zsh": {"_alias": "sh"},
    # ── Markdown ──
    "md": {
        "keyword_categories": {},
        "markdown_rules": True,
    },
    # ── YAML ──
    "yaml": {
        "keyword_categories": {},
        "comment": "#",
        "strings": {'"', "'"},
    },
    "yml": {"_alias": "yaml"},
    # ── TOML ──
    "toml": {
        "keyword_categories": {},
        "comment": "#",
        "strings": {'"'},
    },
    # ── INI ──
    "ini": {
        "keyword_categories": {},
        "comment": ";",
        "strings": set(),
    },
    # ── HTML / XML ──
    "html": {
        "keyword_categories": {},
        "comment": None,
        "strings": {'"', "'"},
        "tag_highlight": True,
    },
    "xml": {"_alias": "html"},
    # ── CSS ──
    "css": {
        "keyword_categories": {},
        "block_comment": ("/*", "*/"),
        "strings": {'"', "'"},
    },
    "scss": {"_alias": "css"},
    "less": {"_alias": "css"},
    # ── Generic fallback ──
    "generic": {
        "keyword_categories": {},
        "comment": "#",
        "strings": {'"', "'"},
    },
}


# ── Static tokenize rules (language-agnostic, priority-ordered) ──
_STATIC_RULES: list[tuple[str, str]] = [
    # Triple-quoted strings / docstrings (Python)
    (r'"""(?:[^"\\]|\\.|"(?!""))*"""', "docstring"),
    (r"'''(?:[^'\\]|\\.|'(?!''))*'''", "docstring"),
    # Double / single quoted strings
    (r'"(?:[^"\\]|\\.)*"', "string"),
    (r"'(?:[^'\\]|\\.)*'", "string"),
    # Template strings (JS)
    (r"`(?:[^`\\]|\\.)*`", "string"),
    # Line comments
    (r"//[^\n]*", "comment"),
    (r"#[^\n]*", "comment"),
    # Block comments (open-ended for single-line diff context)
    (r"/\*[^*]*(?:\*(?!/)[^*]*)*", "comment"),
    # Numbers: hex, binary, float, int
    (r"\b0[xX][0-9a-fA-F]+\b", "number"),
    (r"\b0[bB][01]+\b", "number"),
    (r"\b\d+\.\d+([eE][+-]?\d+)?\b", "number"),
    (r"\b\d+\b", "number"),
    # Function call (identifier before parenthesis)
    (r"\b[a-zA-Z_]\w*(?=\s*\()", "call"),
    # Type names (PascalCase heuristic)
    (r"\b[A-Z][a-zA-Z0-9_]*\b", "type"),
    # Variable / identifier
    (r"\b[a-zA-Z_]\w*\b", "variable"),
    # Multi-char operators
    (r"===|!==|=>|==|!=|<=|>=|\+\+|--|&&|\|\||<<|>>|\*\*|->|\.\.\.", "operator"),
    # Single-char operators
    (r"[+\-*/%=<>!&|^~?:]", "operator"),
    # Punctuation
    (r"[(){}\[\];,.@]", "punct"),
]


# Pre-compile static regexes for performance
_STATIC_RES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), token_type) for pattern, token_type in _STATIC_RULES
]

# Pre-compile hunk-header regexes
_HUNK_RE: re.Pattern[str] = re.compile(
    r"^(@@)\s+(-\d+(?:,\d+)?)\s+(\+\d+(?:,\d+)?)\s+(@@)(.*)$"
)
_HUNK_RANGE_RE: re.Pattern[str] = re.compile(r"(-|\+)(\d+)(,\d+)?")


class SyntaxTokenizer:
    """Per-line syntax tokenizer with language-aware rules and LRU cache."""

    def __init__(self) -> None:
        self._lang_re: dict[str, dict] = {}
        self._token_cache: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self._CACHE_MAX = 512

    # ── language detection ──

    @staticmethod
    def detect_language(filename: str) -> str:
        """Infer language from file extension (raw ext, aliases resolved later)."""
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        if ext in _LANGUAGE_CONFIGS:
            return ext
        return "generic"

    @staticmethod
    @functools.lru_cache(maxsize=256)
    def resolve_color(token_type: str, lang: str) -> tuple[int, int, int]:
        """Return the RGB color for a token type, respecting language overrides."""
        raw = _LANGUAGE_CONFIGS.get(lang, _LANGUAGE_CONFIGS["generic"])
        while "_alias" in raw:
            raw = _LANGUAGE_CONFIGS[raw["_alias"]]

        overrides = raw.get("color_overrides", {})
        if token_type in overrides:
            return overrides[token_type]

        return SYNTAX_COLORS.get(token_type, SYNTAX_COLORS["variable"])

    # ── regex compilation ──

    def _get_lang_re(self, lang: str) -> dict:
        """Return (cached) compiled regex dict for a language."""
        if lang in self._lang_re:
            return self._lang_re[lang]

        raw = _LANGUAGE_CONFIGS.get(lang, _LANGUAGE_CONFIGS["generic"])
        # Resolve aliases
        while "_alias" in raw:
            raw = _LANGUAGE_CONFIGS[raw["_alias"]]

        compiled: dict = {
            "_special_rules": [
                (re.compile(p), t) for p, t in raw.get("special_patterns", [])
            ],
        }

        cats = raw.get("keyword_categories", {})
        for category in ("control", "decl", "storage", "type", "operator"):
            words = cats.get(category, set())
            if words:
                pattern = (
                    r"\b(?:" + "|".join(re.escape(w) for w in sorted(words)) + r")\b"
                )
                compiled[f"_{category}_re"] = re.compile(pattern)

        builtins = raw.get("builtins", set())
        if builtins:
            pattern = (
                r"\b(?:" + "|".join(re.escape(w) for w in sorted(builtins)) + r")\b"
            )
            compiled["_builtin_re"] = re.compile(pattern)

        compiled["_color_overrides"] = raw.get("color_overrides", {})
        compiled["_markdown"] = raw.get("markdown_rules", False)
        self._lang_re[lang] = compiled
        return compiled

    # ── public tokenize ──

    def tokenize(self, line: str, lang: str) -> list[tuple[str, str]]:
        """Tokenize a line of code; results are cached."""
        key = (line, lang)
        if key in self._token_cache:
            return self._token_cache[key]

        config = self._get_lang_re(lang)
        tokens = self._tokenize_impl(line, config)
        tokens = self._merge_adjacent(tokens)

        # Simple LRU eviction
        while len(self._token_cache) >= self._CACHE_MAX:
            self._token_cache.pop(next(iter(self._token_cache)))
        self._token_cache[key] = tokens
        return tokens

    # ── hunk header tokenize ──

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def tokenize_diff_hunk(line: str) -> list[tuple[str, str]]:
        """Tokenize an @@ hunk header line into colored segments."""
        # Example: @@ -45,10 +46,15 @@
        tokens: list[tuple[str, str]] = []
        m = _HUNK_RE.match(line)
        if not m:
            return [(line, "diff_meta")]

        tokens.append((m.group(1), "diff_meta"))  # @@
        tokens.append((" ", "punct"))

        # old range: -45,10
        old_part = m.group(2)
        old_match = _HUNK_RANGE_RE.match(old_part)
        if old_match:
            tokens.append((old_match.group(1), "diff_meta"))
            tokens.append((old_match.group(2), "diff_lineno"))
            if old_match.group(3):
                tokens.append((",", "punct"))
                tokens.append((old_match.group(3)[1:], "diff_count"))
        else:
            tokens.append((old_part, "diff_meta"))

        tokens.append((" ", "punct"))

        # new range: +46,15
        new_part = m.group(3)
        new_match = _HUNK_RANGE_RE.match(new_part)
        if new_match:
            tokens.append((new_match.group(1), "diff_meta"))
            tokens.append((new_match.group(2), "diff_lineno"))
            if new_match.group(3):
                tokens.append((",", "punct"))
                tokens.append((new_match.group(3)[1:], "diff_count"))
        else:
            tokens.append((new_part, "diff_meta"))

        tokens.append((" ", "punct"))
        tokens.append((m.group(4), "diff_meta"))  # @@
        if m.group(5):
            tokens.append((m.group(5), "comment"))  # trailing context

        return tokens

    # ── markdown tokenize ──

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def tokenize_markdown(line: str) -> list[tuple[str, str]]:
        """Tokenize a Markdown line."""
        # Heading: # Title
        m = re.match(r"^(#{1,6})(\s+)(.*)$", line)
        if m:
            return [
                (m.group(1), "keyword"),
                (m.group(2), "punct"),
                (m.group(3), "keyword"),
            ]

        # Horizontal rule
        if re.match(r"^\s*([-*_])\s*\1\s*\1\s*$", line):
            return [(line, "comment")]

        tokens: list[tuple[str, str]] = []
        pos = 0
        # Match bold, italic, inline-code, links
        for match in re.finditer(
            r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[([^\]]+)\]\(([^)]+)\))",
            line,
        ):
            if match.start() > pos:
                tokens.append((line[pos : match.start()], "variable"))

            text = match.group(0)
            if text.startswith("**"):
                tokens.append((text, "keyword"))
            elif text.startswith("*"):
                tokens.append((text, "type"))
            elif text.startswith("`"):
                tokens.append((text, "string"))
            elif text.startswith("["):
                label = match.group(2)
                url = match.group(3)
                tokens.append(("[", "punct"))
                tokens.append((label, "diff_meta"))
                tokens.append(("](", "punct"))
                tokens.append((url, "comment"))
                tokens.append((")", "punct"))

            pos = match.end()

        if pos < len(line):
            tokens.append((line[pos:], "variable"))

        return tokens if tokens else [(line, "variable")]

    # ── multi-line string / comment mask ──

    @staticmethod
    def compute_multiline_mask(lines: list[str], lang: str) -> list[Optional[str]]:
        """Return a mask indicating which lines are inside a multi-line context.

        Each entry is either a token type (e.g. ``"docstring"``, ``"comment"``)
        or ``None``.  Hunk headers (``@@``) reset state because each hunk is a
        non-contiguous region of the source file.
        """
        # Resolve language alias chain to the base language.
        base_lang = lang
        seen = set()
        while (
            base_lang in _LANGUAGE_CONFIGS and "_alias" in _LANGUAGE_CONFIGS[base_lang]
        ):
            if base_lang in seen:
                break
            seen.add(base_lang)
            base_lang = _LANGUAGE_CONFIGS[base_lang]["_alias"]

        mask: list[Optional[str]] = [None] * len(lines)

        if base_lang == "py":
            in_docstring = False
            quote = ""
            for i, line in enumerate(lines):
                if line.startswith("@@"):
                    in_docstring = False
                    quote = ""
                    continue
                if line.startswith("\\"):
                    continue

                content = line[1:] if line and line[0] in "+- " else line
                stripped = content.lstrip()
                if not in_docstring:
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        quote = '"""' if stripped.startswith('"""') else "'''"
                        if stripped.find(quote, len(quote)) == -1:
                            in_docstring = True
                            mask[i] = "docstring"
                else:
                    mask[i] = "docstring"
                    if quote in content:
                        in_docstring = False
                        quote = ""

        elif _LANGUAGE_CONFIGS.get(base_lang, {}).get("block_comment") == ("/*", "*/"):
            in_block = False
            for i, line in enumerate(lines):
                if line.startswith("@@"):
                    in_block = False
                    continue
                if line.startswith("\\"):
                    continue

                content = line[1:] if line and line[0] in "+- " else line
                if not in_block:
                    start = content.find("/*")
                    if start != -1:
                        end = content.find("*/", start + 2)
                        if end == -1:
                            in_block = True
                            mask[i] = "comment"
                else:
                    mask[i] = "comment"
                    if "*/" in content:
                        in_block = False

        return mask

    # ── internal tokenize implementation ──

    def _tokenize_impl(self, line: str, config: dict) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        pos = 0
        special_rules = config.get("_special_rules", [])

        while pos < len(line):
            matched = False

            # 1. Special patterns (language-specific, e.g. Rust lifetime)
            for pattern_re, token_type in special_rules:
                m = pattern_re.match(line, pos)
                if m:
                    tokens.append((m.group(0), token_type))
                    pos += len(m.group(0))
                    matched = True
                    break
            if matched:
                continue

            # 2. Keyword categories (control > decl > storage > type > operator)
            for category in ("control", "decl", "storage", "type", "operator"):
                regex = config.get(f"_{category}_re")
                if regex:
                    m = regex.match(line, pos)
                    if m:
                        tokens.append((m.group(0), f"keyword_{category}"))
                        pos += len(m.group(0))
                        matched = True
                        break
            if matched:
                continue

            # 3. Builtins
            builtin_re = config.get("_builtin_re")
            if builtin_re:
                m = builtin_re.match(line, pos)
                if m:
                    tokens.append((m.group(0), "builtin"))
                    pos += len(m.group(0))
                    continue

            # 4. Static rules (strings, comments, numbers, calls, types, vars, ops, punct)
            for pattern_re, token_type in _STATIC_RES:
                m = pattern_re.match(line, pos)
                if m:
                    tokens.append((m.group(0), token_type))
                    pos += len(m.group(0))
                    matched = True
                    break

            if not matched:
                tokens.append((line[pos], "punct"))
                pos += 1

        return tokens

    # ── merge adjacent tokens of same type ──

    @staticmethod
    def _merge_adjacent(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
        if not tokens:
            return []
        merged: list[tuple[str, str]] = [tokens[0]]
        for text, ttype in tokens[1:]:
            last_text, last_type = merged[-1]
            if ttype == last_type:
                merged[-1] = (last_text + text, last_type)
            else:
                merged.append((text, ttype))
        return merged
