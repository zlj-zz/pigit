from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from functools import lru_cache
from collections.abc import Iterator, Mapping


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard."""
    platform = sys.platform
    try:
        if platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True
        elif platform == "win32":
            subprocess.run(["clip"], input=text.encode(), check=True)
            return True
        else:
            # Try wl-copy (Wayland) first, then xclip (X11)
            try:
                subprocess.run(
                    ["wl-copy"], input=text.encode(), check=True, capture_output=True
                )
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(),
                    check=True,
                    capture_output=True,
                )
                return True
    except Exception:
        return False


@lru_cache(maxsize=256)
def relative_time(unix_ts: int) -> str:
    """Return a human-readable relative time string."""
    delta = int(time.time()) - unix_ts
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    if delta < 604800:
        return f"{delta // 86400}d ago"
    return f"{delta // 604800}w ago"


def strtobool(s: str) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    Raises:
        ValueError: if val is anything else.

    Returns:
        bool

    Docs Test:
        >>> strtobool('y')
        True
        >>> strtobool('Y')
        True
        >>> strtobool('n')
        False
        >>> strtobool('N')
        False
    """
    s = s.lower()

    if s in {"y", "yes", "t", "true", "on", "1"}:
        return True
    elif s in {"n", "no", "f", "false", "off", "0"}:
        return False
    else:
        raise ValueError("Not support string.")


def split_at_most(raw: str, max_tokens: int, hint: str) -> list[str]:
    """Split ``raw`` on whitespace honouring quotes; bound the token count.

    Raises:
        ValueError: When the input is empty, misquoted, or has more than
            ``max_tokens`` tokens (message hints the expected shape).
    """
    try:
        parts = shlex.split(raw)
    except ValueError as exc:
        raise ValueError(f"bad quoting: {exc}") from None
    if not parts:
        raise ValueError("empty input")
    if len(parts) > max_tokens:
        raise ValueError(f"expected: {hint}")
    return parts


def traceback_info(extra_msg: str = "null") -> str:
    """Get traceback information.

    Args:
        extra_msg (str, optional): extra custom message. Defaults to "null".

    Returns:
        str: formatted traceback information.
    """
    exc_type, exc_value, exc_obj = sys.exc_info()
    if exc_type is None or exc_value is None or exc_obj is None:
        return ""

    err_value = exc_type.__name__
    lineno = exc_obj.tb_lineno
    filename = exc_obj.tb_frame.f_code.co_filename

    return (
        f"File {filename}, line {lineno}, {err_value}:{exc_value}, remark:[{extra_msg}]"
    )


def confirm(text: str = "Confirm[y/n]:", default: bool = True) -> bool:
    """Obtain confirmation results.
    Args:
        text (str): Confirmation prompt.
        default (bool): Result returned when unexpected input.

    Returns:
        (bool): Confirm result.
    """
    input_command: str = input(text).strip().lower()

    if input_command in {"n", "no", "N", "No"}:
        return False
    elif input_command in {"y", "yes", "Y", "Yes"}:
        return True
    else:
        return default


# Mark the type corresponding to the file suffix.
# abcdefg hijklmn opq rst uvw xyz
SUFFIX_TYPE: dict[str, str] = {
    "": "",
    "bat": "Batch",
    "c": "C",
    "cfg": "Properties",
    "conf": "Properties",
    "cpp": "C++",
    "cs": "C#",
    "css": "CSS",
    "dart": "Dart",
    "dea": "XML",
    "go": "Go",
    "gradle": "Groovy",
    "h": "C",
    "hpp": "C++",
    "htm": "HTML",
    "html": "HTML",
    "ini": "Ini",
    "java": "Java",
    "js": "Java Script",
    "json": "Json",
    "jsx": "React",
    "kt": "Kotlin",
    "launch": "XML",
    "less": "CSS",
    "lua": "Lua",
    "log": "Log",
    "m": "Object-C",
    "mm": "Object-C++",
    "markdown": "Markdown",
    "md": "Markdown",
    "msg": "ROS Message",
    "php": "PHP",
    "plist": "XML",
    "properties": "Properties",
    "py": "Python",
    "r": "R",
    "rb": "Ruby",
    "rc": "Properties",
    "rs": "Rust",
    "rst": "reStructuredText",
    "ts": "Type Script",
    "tsx": "React",
    "sass": "CSS",
    "scss": "CSS",
    "sh": "Shell",
    "sql": "SQL",
    "srv": "ROS Message",
    "swift": "Swift",
    "toml": "Properties",
    "vb": "Visual Basic",
    "vim": "Vim Script",
    "vue": "Vue",
    "xhtml": "HTML",
    "xml": "XML",
    "yaml": "YAML",
    "yml": "YAML",
    "zsh": "Shell",
}

# Mark the type of some special files.
SPECIAL_NAMES: dict[str, str] = {
    "license": "LICENSE",
    "requirements.txt": "Pip requirement",
    "vimrc": "Vim Script",
    "dockerfile": "Docker",
}


def adjudgment_type(file: str, original: bool = False) -> str:
    """Get file type.

    First, judge whether the file name is special, and then query the
    file suffix. Otherwise, the suffix or name will be returned as is.

    Args:
        file (str): file name string.
        original (bool, option): whether return origin when match failed.

    Returns:
        (str): file type.

    Docs test
        >>> adjudgment_type('py')
        'Python'
        >>> adjudgment_type('xx')
        'unknown'
        >>> adjudgment_type('xx', True)
        'xx'
    """
    if pre_type := SPECIAL_NAMES.get(file.lower()):
        return pre_type

    suffix = file.split(".")[-1]
    if suffix_type := SUFFIX_TYPE.get(suffix.lower()):
        return suffix_type
    else:
        return suffix if original else "unknown"


FILE_ICONS: dict[str, str] = {
    "": "",
    "Batch": "",
    "C": "",
    "C#": "",
    "C++": "",
    "CSS": "",
    "Dart": "",
    "Groovy": "",
    "Go": "",
    "HTML": "",
    "Java": "",
    "Java Script": "",
    "Lua": "",
    "Kotlin": "",
    "Markdown": "",
    "PHP": "",
    "Properties": "",
    "Python": "",
    "R": "ﳒ",
    "React": "",
    "Ruby": "",
    "Rust": "",
    "ROS Message": "",
    "reStructuredText": "",
    "Shell": "",
    "Swift": "",
    "SQL": "",
    "snippets": "",
    "Type Script": "",
    "Vim Script": "",
    "Vue": "﵂",
    "YAML": "",
    "XML": "",
}


def get_file_icon(file_type: str) -> str:
    """According file type return icon.

    Args:
        file_type (str): type string.

    Returns:
        str: icon.

    Docs test
        >>> get_file_icon('Python')
        ''
        >>> get_file_icon('xx')
        ''
    """
    #     
    return FILE_ICONS.get(file_type, "")


# ── Nerd Font detection and fallback ──
# PUA glyphs render as tofu blocks on terminals without a Nerd Font, so the
# icons policy defaults to ``auto``: enable only when the terminal advertises
# NF support, else fall back to single-cell plain symbols.

_DIR_ICON = "\uf07b"  # nf-fa-folder (PUA block, width 1)
# Fallback symbols are single-cell (wcswidth 1, pinned by tests). They are
# East Asian Ambiguous (A) class; pigit's wcwidth_table renders them 1 cell.
_FALLBACK_DIR = "▸"  # U+25B8
_FALLBACK_FILE = "·"  # U+00B7

_NF_MARKER_ENV = (
    "KITTY_WINDOW_ID",  # kitty
    "WEZTERM_EXECUTABLE",  # WezTerm
    "ALACRITTY_WINDOW_ID",  # Alacritty
    "GHOSTTY_RESOURCES_DIR",  # Ghostty
)
_NF_TERM_PROGRAMS = {"WezTerm", "ghostty", "kitty"}


def resolve_nerd_icons(policy: str, env: Mapping | None = None) -> bool:
    """Resolve the icons policy to a concrete on/off decision.

    ``on`` / ``off`` force the outcome; ``auto`` uses env-marker heuristics —
    terminals known to ship a Nerd Font (kitty/WezTerm/Alacritty/Ghostty)
    opt in, everything else falls back to plain symbols (tofu is worse than
    a plain glyph). ``env`` is injectable for tests; defaults to os.environ.

    Args:
        policy: "auto", "on" or "off".
        env: Environment mapping to probe, or None for os.environ.

    Returns:
        True when Nerd Font glyphs should be rendered.
    """
    if policy == "on":
        return True
    if policy == "off":
        return False
    env = os.environ if env is None else env
    return any(env.get(m) for m in _NF_MARKER_ENV) or (
        env.get("TERM_PROGRAM") in _NF_TERM_PROGRAMS
    )


def resolve_icon(nerd_enabled: bool, file_type: str, is_dir: bool = False) -> str:
    """Return a 1-cell icon prefix: NF glyph when available, else a plain
    fallback symbol. Single resolution point over ``get_file_icon``.

    Args:
        nerd_enabled: Whether Nerd Font glyphs are usable.
        file_type: File type string (see :func:`adjudgment_type`).
        is_dir: True for directory rows.

    Returns:
        The icon glyph or fallback symbol (never empty).
    """
    if nerd_enabled:
        return _DIR_ICON if is_dir else get_file_icon(file_type)
    return _FALLBACK_DIR if is_dir else _FALLBACK_FILE


def page_output(text: str | Iterator[str]) -> None:
    """Send *text* or a generator of chunks to a pager if stdout is a TTY.

    Respects the ``PAGER`` environment variable; defaults to ``less -R``
    so ANSI colors are preserved.
    """
    is_str = isinstance(text, str)

    if not sys.stdout.isatty():
        if is_str:
            print(text, end="")
        else:
            for chunk in text:
                print(chunk, end="")
        return

    pager = os.environ.get("PAGER", "less -FRX")
    try:
        proc = subprocess.Popen(
            shlex.split(pager),
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
        )
        if is_str:
            proc.communicate(text.encode("utf-8", "replace"))
        else:
            stdin = proc.stdin
            assert stdin is not None
            try:
                for chunk in text:
                    stdin.write(chunk.encode("utf-8", "replace"))
                    stdin.flush()
            except BrokenPipeError:
                pass
            finally:
                try:
                    stdin.close()
                except BrokenPipeError:
                    pass
                proc.wait()
    except (OSError, subprocess.SubprocessError):
        if is_str:
            print(text, end="")
        else:
            for chunk in text:
                print(chunk, end="")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
