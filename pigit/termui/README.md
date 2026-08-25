# `pigit.termui`

Lightweight, keyboard-first terminal UI for full-screen apps and modal overlays.

**Requires Python 3.11+.**

For architecture, export rules, and contribution guidance, see
[`DEVELOPMENT.md`](DEVELOPMENT.md).

## Tiered imports

Root `__init__` is the **stable façade** (what you use for app wiring). Domain
packages hold widgets, layout, and helpers — do not expect those classes on the
root.

```python
from pigit.termui import Application, Component, show_toast, set_theme, palette
from pigit.termui.widgets import ItemList, Footer, Sheet, CommandPalette
from pigit.termui.containers import Column, Row, TabView, SplitPane
from pigit.termui.reactive import Signal
from pigit.termui.primitives import plain, tokenize_with_positions, format_line_number
from pigit.termui.syntax import SyntaxTokenizer
from pigit.termui.event_bus import EventBus
```

| Import from | Use for |
|-------------|---------|
| `pigit.termui` | App skeleton, overlays helpers, Theme, Surface/Segment, bindings, mouse/async |
| `pigit.termui.widgets` | Concrete UI widgets (lists, sheets, toasts, chrome, …) |
| `pigit.termui.containers` | Layout (`Row`, `Column`, `TabView`, `SplitPane`) |
| `pigit.termui.primitives` | Text/frame/ANSI/word-diff/gutter/calendar helpers |
| `pigit.termui.reactive` | `Signal`, `Computed` |
| `pigit.termui.syntax` | `SyntaxTokenizer` |
| `pigit.termui.event_bus` | `EventBus` |

Exact root names live in `pigit.termui.__all__` and are locked by tests.

## Minimal example

Run from a real TTY. Subclass `Application`, build a root component, quit on `q`:

```python
from pigit.termui import Application, Component, ExitEventLoop, bind_action


class DemoPanel(Component):
    NAME = "demo"

    def paint(self, surface):
        surface.draw_text_rgb(
            0,
            0,
            "termui demo — press q to quit",
            fg=(220, 220, 230),
            bg=(18, 18, 22),
        )


class DemoApp(Application):
    @bind_action("quit", "q", desc="Quit")
    def quit(self) -> None:
        raise ExitEventLoop("bye")

    def build_root(self):
        return DemoPanel()


if __name__ == "__main__":
    DemoApp().run()
```

Prefer `keys.KEY_*` constants for special keys. Full Git TUI wiring lives in
`pigit.app` (`PigitApplication`).

## Root public API (façade)

| Category | Names |
|----------|-------|
| **App skeleton** | `Application`, `ComponentRoot`, `Component`, `ComponentError`, `ExitEventLoop` |
| **Compose** | `bind_signals`, `render_child`, `resolve_presentation_leaf` |
| **Bindings** | `Binding`, `BindingError`, `bind_action`, `collect_action_bindings`, `set_key_overrides`, `keys` |
| **Theme / palette** | `Theme`, `DEFAULT_THEME`, `get_theme`, `set_theme`, `palette` |
| **Drawing contract** | `Surface`, `Segment` |
| **Overlay helpers** | `show_toast`, `show_sheet`, `dismiss_sheet`, `dismiss_toast`, `show_badge`, `get_badge`, `get_badge_signal`, `show_spinner`, `hide_spinner`, `exec_external` |
| **Runtime** | `request_render`, `by_id`, `get_registry`, `get_focus_manager`, `get_renderer`, `get_renderer_strict` |
| **Input / async** | `MouseButton`, `MouseEvent`, `MouseKind`, `AsyncTask`, `run_async` |
| **Types** | `EventType`, `EVT_GOTO`, `EVT_SELECTION_CHANGED`, `LayerKind`, `OverlayDispatchResult`, `ToastPosition`, `FeedbackKind` |

**Not on root** (import from the domain package instead):

- Widget classes (`Toast`, `Sheet`, `Popup`, `AlertDialog`, `HelpPanel`, …) → `widgets`
- `plain`, `BoxFrame`, `parse_ansi_line`, word-diff / gutter / calendar helpers → `primitives`
- `SyntaxTokenizer` → `syntax`
- `Renderer` → `renderer` (advanced)

## Widgets and containers

```python
from pigit.termui.widgets import (
    AlertDialog,
    BorderedBrowser,
    CheckList,
    CommandPalette,
    Footer,
    Header,
    HeatmapGrid,
    HelpPanel,
    InputLine,
    ItemList,
    LineTextBrowser,
    LintBar,
    Popup,
    Sheet,
    StatusBar,
    StepLineChart,
    Toast,
)
from pigit.termui.containers import Column, Row, SplitPane, TabView
```

## Common patterns

### Overlay feedback

```python
from pigit.termui import show_toast, show_badge, FeedbackKind

show_toast("Saved", kind=FeedbackKind.SUCCESS)
show_badge("syncing…")
```

### Actions and keys

```python
from pigit.termui import bind_action, keys

@bind_action("next", "j", keys.KEY_DOWN, desc="Next item", tip="Next")
def next(self):
    ...
```

- `action` — stable id (remappable via app keybinding config).
- `desc` / `tip` — help text and footer hint.
- `BINDINGS = [("q", "quit")]` remains valid for simple pairs without metadata.

### Segments and palette

```python
from pigit.termui import Segment, palette

segments = [
    Segment("main", fg=palette.DEFAULT_FG, style_flags=palette.STYLE_BOLD),
    Segment("  hint", fg=palette.DEFAULT_FG_DIM),
]
surface.draw_segments(row, col, segments)
```

Use `palette` for colors and style flags; use `keys` for semantic key constants.

### Theme

```python
from pigit.termui import set_theme, get_theme, Theme

set_theme(my_theme)   # typically in Application.__init__
theme = get_theme()
```

### Primitives (text / diff helpers)

```python
from pigit.termui.primitives import (
    plain,
    tokenize_with_positions,
    merge_ranges,
    format_line_number,
    build_contribution_calendar,
)
```

## Next steps

- Build a real app: subclass `Application`, compose `widgets` + `containers`.
- Reference implementation: `pigit/app.py` and panel modules.
- Changing the framework itself: [`DEVELOPMENT.md`](DEVELOPMENT.md).
