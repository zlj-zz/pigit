"""
Module: pigit/handlers/cmd_picker.py
Description: Interactive picker for cmd commands (--pick functionality).
Author: Zev
Date: 2026-04-10
"""

from __future__ import annotations

import os
import shlex
import sys
from typing import TYPE_CHECKING, cast

from pigit.termui import (
    Component,
    ComponentRoot,
    ExitEventLoop,
    keys,
    get_renderer_strict,
    palette,
)
from pigit.termui._segment import Segment
from pigit.termui.containers import Column
from pigit.termui.wcwidth_table import wcswidth
from pigit.termui.widgets import InputLine, ItemList, StatusBar
from pigit.termui.tty_io import (
    terminal_size,
    truncate_line,
    tty_ok,
)
from pigit.picker_app import (
    BasePickerApp,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
)

from pigit.git.cmds._completion import make_candidate_provider
from pigit.git.cmds._mru import load_mru
from .cmd_picker_data import (
    iter_cmd_new_entries,
    CmdNewEntry,
    build_context_signals,
    sort_picker_entries,
)

if TYPE_CHECKING:
    from pigit.git.cmds import GitCommandNew

NO_TTY_MSG = (
    "@red(pigit cmd --pick) needs an interactive terminal.\n"
    "Use `pigit cmd -l` for the full list or "
    "`pigit cmd -s <query>` to search.\n"
    "See `pigit cmd -h` for more options."
)

_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit cmd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "`pigit cmd -l` / `pigit cmd -s <query>`."
)

# Tests can patch this
_tty_ok = tty_ok


def _highlight_match(
    text: str,
    needle: str,
    *,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int] | None = None,
) -> list[Segment]:
    """Split text into Segments with matched chars highlighted."""
    if not needle:
        return [Segment(text, fg=fg, bg=bg)]

    segments: list[Segment] = []
    lower_text = text.lower()
    lower_needle = needle.lower()
    t_idx = 0
    n_idx = 0

    while t_idx < len(text) and n_idx < len(needle):
        pos = lower_text.find(lower_needle[n_idx], t_idx)
        if pos == -1:
            break
        if pos > t_idx:
            segments.append(Segment(text[t_idx:pos], fg=fg, bg=bg))
        segments.append(
            Segment(
                text[pos],
                fg=palette.CYAN,
                bg=bg,
                style_flags=palette.STYLE_BOLD | palette.STYLE_UNDERLINE,
            )
        )
        t_idx = pos + 1
        n_idx += 1

    if t_idx < len(text):
        segments.append(Segment(text[t_idx:], fg=fg, bg=bg))
    return segments


# ---------------------------------------------------------------------------
# Picker implementation using Application facade + generic components
# ---------------------------------------------------------------------------


def run_cmd_new_picker(
    processor: GitCommandNew | None = None,
    *,
    pick_alt_screen: bool = False,
    category: str | None = None,
    print_only: bool = False,
) -> tuple[int, str | None]:
    """Run interactive picker for cmd commands.

    Args:
        processor: GitCommandNew instance (created if None)
        pick_alt_screen: Use alternate screen buffer
        category: Optional category filter (e.g., "branch", "commit")
        print_only: Print command instead of executing

    Returns:
        (exit_code, message) tuple
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    # Import here to avoid circular imports at module level
    from pigit.git.cmds import GitCommandNew

    processor = processor or GitCommandNew()

    # 1. Data preparation
    entries = [
        e
        for e in iter_cmd_new_entries()
        if not category or e.category.lower() == category.lower()
    ]

    mru = load_mru()
    signals = build_context_signals()
    entries = sort_picker_entries(entries, mru, signals)
    mru_set = set(mru) if mru else set()

    rows: list[PickerRow] = [
        PickerRow(title=e.name, detail=f"[{e.category}] {e.help_text}", ref=e)
        for e in entries
    ]

    pick_suffix = f" {category}" if category else ""
    mode_hint = "print" if print_only else "run"
    title = (
        f"pigit cmd --pick{pick_suffix}  "
        f"[j/k scroll  Enter {mode_hint}  ? preview  / filter  q/Esc quit]"
    )

    # 2. Custom selector with category-aware rendering
    class _CmdItemList(ItemList):
        def __init__(
            self,
            app,
            **kwargs,
        ) -> None:
            super().__init__(**kwargs)
            self._app = app

        def describe_row(
            self,
            idx: int,
            is_cursor: bool,
            *,
            item_idx: int | None = None,
            sub_row: int = 0,
        ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
            app = self._app
            cols = self._size[0]

            if idx in app._separator_indices:
                sep_text = self.content[idx]
                sep_w = wcswidth(sep_text)
                if sep_w < cols:
                    sep_text = sep_text + "─" * (cols - sep_w)
                return ([], [Segment(sep_text, fg=palette.DIM)], [])

            row = app._row_data[idx]
            assert row is not None
            ent = cast(CmdNewEntry, row.ref)

            bg = palette.BG_HOVER if is_cursor else None
            row_style = palette.STYLE_BOLD if is_cursor else 0
            in_mru = ent.name in app._mru_set

            if in_mru:
                left = [
                    Segment(
                        "◆ ",
                        fg=palette.CYAN,
                        bg=bg,
                        style_flags=palette.STYLE_BOLD | row_style,
                    )
                ]
            elif ent.is_dangerous:
                left = [Segment("⚠ ", fg=palette.YELLOW, bg=bg, style_flags=row_style)]
            else:
                left = [
                    Segment("  ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style)
                ]

            name_fg = palette.CYAN if in_mru else palette.DEFAULT_FG
            name_style = palette.STYLE_BOLD if in_mru else 0

            name_segs = _highlight_match(
                ent.name, app._filter_needle, fg=name_fg, bg=bg
            )
            for seg in name_segs:
                seg.style_flags |= name_style | row_style

            name_w = sum(wcswidth(s.text) for s in name_segs)
            name_pad = 15 - name_w
            if name_pad > 0:
                name_segs.append(
                    Segment(
                        " " * name_pad,
                        fg=palette.DEFAULT_FG,
                        bg=bg,
                        style_flags=row_style,
                    )
                )

            help_segs = _highlight_match(
                ent.help_text, app._filter_needle, fg=palette.DEFAULT_FG_DIM, bg=bg
            )
            for seg in help_segs:
                seg.style_flags |= row_style
            main = (
                name_segs
                + [Segment("  ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style)]
                + help_segs
            )

            return (left, main, [])

    # 3. Local Application (used only inside this function)
    class _CmdPickerApp(BasePickerApp):
        def __init__(self) -> None:
            super().__init__()
            self._state = PickerState()
            self._mode = PickerMode.BROWSE
            self._number_buf: str | None = None
            self._print_only = print_only
            self._processor = processor
            self._rows = rows
            self._filtered_rows = list(rows)
            self._pending_entry: CmdNewEntry | None = None
            self._last_needle: str = ""
            self._mru_set = mru_set
            self._separator_indices: set[int] = set()
            self._row_data: list[PickerRow | None] = []
            self._filter_needle = ""
            self._collapsed_groups: set[str] = set()
            self._sep_category_map: dict[int, str] = {}

        def get_title(self) -> str:
            return title

        def build_root(self) -> Component:
            self._header = PickerHeader(self.get_title())
            content, row_data, sep_indices, sep_cats = self._build_grouped_content(
                self._filtered_rows,
                collapsed_groups=self._collapsed_groups,
            )
            self._row_data = row_data
            self._separator_indices = sep_indices
            self._sep_category_map = sep_cats
            self._list = _CmdItemList(
                self,
                content=content,
                on_selection_changed=lambda idx: self._state.selected_idx.set(idx),
            )
            self._list.set_skip_indices(sep_indices)
            self._status = StatusBar(self._state.status_text)
            self._input = self.build_input()

            self._layout = Column(
                [self._header, self._list, self._status, self._input],
                heights=[2, "flex", 1, 0],
            )
            return self._layout

        def build_input(self) -> InputLine:
            return InputLine(
                prompt="/",
                overlay_mode=True,
                visible=False,
                on_value_changed=self._on_filter_value_changed,
                on_submit=self._on_input_submit,
                on_cancel=self._on_input_cancel,
            )

        def _build_grouped_content(
            self,
            rows: list[PickerRow],
            *,
            collapsed_groups: set[str] | None = None,
        ) -> tuple[list[str], list[PickerRow | None], set[int], dict[int, str]]:
            content: list[str] = []
            row_data: list[PickerRow | None] = []
            separators: set[int] = set()
            sep_categories: dict[int, str] = {}
            last_cat = None
            collapsed = collapsed_groups or set()
            for r in rows:
                ent = cast(CmdNewEntry, r.ref)
                cat = ent.category
                if cat != last_cat:
                    prefix = "▸" if cat in collapsed else "─"
                    content.append(f"{prefix}── {cat} ")
                    row_data.append(None)
                    sep_idx = len(content) - 1
                    separators.add(sep_idx)
                    sep_categories[sep_idx] = cat
                    last_cat = cat
                if cat in collapsed:
                    continue
                content.append(
                    f"{'⟲' if ent.name in self._mru_set else ' '}"
                    f"{'▲' if ent.is_dangerous else ' '}"
                    f" {ent.name:<15} {ent.help_text}"
                )
                row_data.append(r)
            return content, row_data, separators, sep_categories

        def setup_root(self, root: ComponentRoot) -> None:
            self._update_status()
            if self._help_popup is not None:
                panel = self._help_popup._child
                panel._entries_source = None
                panel.set_entries(self._help_entries())

        def _help_entries(self) -> list[tuple[str, str]]:
            return [
                ("j / k", "Scroll up / down"),
                ("g / G", "Jump to first / last"),
                ("Tab", "Toggle group fold"),
                ("Enter", "Confirm / enter params"),
                ("/", "Filter list"),
                ("?", "Show preview"),
                ("q / Esc", "Quit"),
                ("Ctrl+C", "Abort"),
                ("0-9", "Goto number"),
            ]

        def get_terminal_too_small_msg(self) -> str:
            return _TERMINAL_TOO_SMALL_MSG

        def on_key(self, key: str) -> None:
            if self._number_buf is not None:
                self._on_number_prefix(key)
                return
            if self._mode == PickerMode.PARAM_INPUT:
                self._input.on_key(key)
                return
            if self._input.is_visible:
                self._input.on_key(key)
                return
            self._on_browse(key)

        def on_confirm(self) -> None:
            self._enter_param_input()

        def _on_browse(self, key: str) -> None:
            if key in ("j", keys.KEY_DOWN):
                self._list.next()
            elif key in ("k", keys.KEY_UP):
                self._list.previous()
            elif key == "g":
                self._jump_to_first()
            elif key == "G":
                self._jump_to_last()
            elif key == keys.KEY_TAB:
                self._toggle_group_at_cursor()
            elif key == "enter":
                self._enter_param_input()
            elif key == "/":
                self._input._enter_overlay_mode()
                self._layout.set_heights([2, "flex", 1, 1])
            elif key in ("q", keys.KEY_ESC):
                self.quit()
            elif key == "?":
                self._show_preview()
            elif len(key) == 1 and key.isdigit():
                self._number_buf = key
                self._echo_number(key)

        def _jump_to_first(self) -> None:
            self._list.curr_no = 0
            self._list._scroll_into_view()
            self._list._notify_change()

        def _jump_to_last(self) -> None:
            n = len(self._list.content)
            if n == 0:
                return
            self._list.curr_no = n - 1
            self._list._scroll_into_view()
            self._list._notify_change()

        def _on_number_prefix(self, key: str) -> None:
            buf = self._number_buf
            assert buf is not None
            if key == "enter":
                self._number_buf = None
                self._clear_number_echo()
                try:
                    num = int(buf)
                except ValueError:
                    return
                if 1 <= num <= len(self._list.content):
                    self._list.curr_no = num - 1
                    self._enter_param_input()
            elif key == keys.KEY_ESC:
                self._number_buf = None
                self._clear_number_echo()
            elif len(key) == 1 and key.isdigit():
                self._number_buf = buf + key
                self._echo_number(self._number_buf)
            else:
                self._number_buf = None
                self._clear_number_echo()

        # --- Filter mode ---

        def _on_filter_value_changed(self, text: str) -> None:
            self._state.filter_text.set(text)
            self._apply_filter()

        def _apply_filter(self) -> None:
            needle = self._input.value
            if needle == self._last_needle:
                return
            needle_lower = needle.lower()
            self._last_needle = needle
            self._filter_needle = needle_lower
            filtered = [
                r
                for r in self._rows
                if needle_lower in r.title.lower()
                or needle_lower in (r.detail or "").lower()
            ]
            self._filtered_rows = filtered
            self._sync_content(filtered, reset_cursor=True)

        def _sync_content(
            self, rows: list[PickerRow], *, reset_cursor: bool = False
        ) -> None:
            content, row_data, sep_indices, sep_cats = self._build_grouped_content(
                rows,
                collapsed_groups=self._collapsed_groups if reset_cursor else None,
            )
            self._row_data = row_data
            self._separator_indices = sep_indices
            self._sep_category_map = sep_cats
            self._list.set_content(content)
            self._list.set_skip_indices(sep_indices)
            if reset_cursor:
                self._list.curr_no = 0
                self._state.selected_idx.set(0)
            else:
                n = len(content)
                if self._list.curr_no >= n:
                    self._list.curr_no = max(0, n - 1)
                self._state.selected_idx.set(self._list.curr_no)
            self._update_status()

        def _rebuild_content(self) -> None:
            self._sync_content(self._filtered_rows, reset_cursor=False)

        def _toggle_group_at_cursor(self) -> None:
            idx = self._list.curr_no
            cat = self._sep_category_map.get(idx)
            if cat is None:
                return
            if cat in self._collapsed_groups:
                self._collapsed_groups.discard(cat)
            else:
                self._collapsed_groups.add(cat)
            self._rebuild_content()

        # --- Param input mode ---

        def _enter_param_input(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._row_data):
                return
            row = self._row_data[idx]
            if row is None:
                return
            ent = row.ref
            assert isinstance(ent, CmdNewEntry)

            if not ent.has_args:
                self._finish_execute(ent, "")
                return

            self._pending_entry = ent
            self._mode = PickerMode.PARAM_INPUT
            self._input.set_prompt(f"{ent.name} ")
            self._input.set_value("")
            self._input.set_candidate_provider(
                make_candidate_provider(ent.arg_completion)
            )
            self._input.set_visible(True)
            self._layout.set_heights([2, "flex", 1, 1])

        def _exit_param_input(self) -> None:
            self._mode = PickerMode.BROWSE
            self._pending_entry = None
            self._input.set_candidate_provider(None)
            self._input.clear()
            self._input.set_prompt("/")
            self._input.set_visible(False)
            self._layout.set_heights([2, "flex", 1, 0])

        def _on_input_submit(self, value: str) -> None:
            if self._mode == PickerMode.PARAM_INPUT:
                assert self._pending_entry is not None
                self._finish_execute(self._pending_entry, value)
            else:
                # Filter mode — hide input line so focus returns to the list.
                self._input._visible = False
                self._layout.set_heights([2, "flex", 1, 0])

        def _on_input_cancel(self) -> None:
            if self._mode == PickerMode.PARAM_INPUT:
                self._exit_param_input()
            self._input.clear()
            if not self._input._visible:
                self._layout.set_heights([2, "flex", 1, 0])

        # --- Business logic ---

        def _finish_execute(self, ent: CmdNewEntry, extra_raw: str) -> None:
            extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
            if self._print_only:
                cmd_parts = ["pigit", "cmd", ent.name, *extra_args]
                result = shlex.join(cmd_parts)
                raise ExitEventLoop("done", exit_code=0, result_message=result)
            exit_code, output = self._processor.execute(ent.name, extra_args)
            raise ExitEventLoop("done", exit_code=exit_code, result_message=output)

        def _update_status(self) -> None:
            n = len(self._list.content)
            cat_count = len({cast(CmdNewEntry, e.ref).category for e in self._rows})
            text = f"{n} commands · {cat_count} categories"
            self._state.status_text.set(text)

        def _show_preview(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._row_data):
                return
            row = self._row_data[idx]
            if row is None:
                return
            ent = row.ref
            assert isinstance(ent, CmdNewEntry)
            preview = self._processor.preview(ent.name, [])
            if preview[1]:
                self._status.set_text(f"preview: {preview[1]}")

        def _echo_number(self, buf: str) -> None:
            renderer = get_renderer_strict()
            cols, _ = terminal_size()
            line = truncate_line(f"# {buf} — Enter to confirm", cols)
            renderer.draw_absolute_row(1, line)

        def _clear_number_echo(self) -> None:
            renderer = get_renderer_strict()
            cols, _ = terminal_size()
            renderer.draw_absolute_row(1, " " * cols)

    # 3. Launch
    exit_code, message = _CmdPickerApp().run_with_result()

    # print_only output is handled after Application exits so it lands on
    # the main screen, not inside the alternate screen buffer.
    if print_only and message is not None:
        widget_output = os.environ.get("PIGIT_WIDGET_OUTPUT")
        if widget_output:
            try:
                with open(widget_output, "w", encoding="utf-8") as f:
                    f.write(message + "\n")
            except OSError as exc:
                return 1, f"Failed to write widget output: {exc}"
        else:
            sys.stdout.write(message + "\n")
            sys.stdout.flush()
        return 0, None

    return exit_code, message
