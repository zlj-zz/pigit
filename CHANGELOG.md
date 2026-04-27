# Changelog of pigit

## 1.8.4 (2026-04-27)

### App

- **Inspector update logic sunk to `InspectorPanel`**: `update_from(source)` handles `(id(source), curr_no)` caching and `get_inspector_data()` dispatch; app layer deletes `_update_inspector_content()` and `_last_inspector_key` state.
- **`FlatTheme.bg_palette`**: command palette background color moved from local `_PALETTE_BG = (45, 45, 50)` into the theme system.
- **`CommitPanel._max_meta_w` initialized in `__init__`**: explicit `self._max_meta_w = 0` removes the need for defensive `getattr(..., 0)` in `describe_row`.

### TermUI

- **`LoopKwargs` TypedDict**: `Application.__init__(**loop_kwargs: Unpack[LoopKwargs])` declares the forwarded `AppEventLoop` keyword arguments for type-checker validation.
- **`Application._root` explicitly declared**: `self._root: Optional[ComponentRoot] = None` added to `__init__`.
- **Surface `draw_text_rgb` performance**: pre-computes `wcswidth` before the hot loop, ASCII fast path bypasses per-char `_char_width` calls, `_SPACER_CELL` constant avoids repeated `FlatCell("")` allocations.
- **Unused import cleanup**: removed `Callable`, `LayerKind`, `palette`, `subprocess`, and stale `TYPE_CHECKING` blocks across `app.py`, `_application.py`, `_layout.py`, `_text.py`.

### Git

- **Merge command branch completion**: `m`, `m.no`, `m.ff`, `m.squash` gain `arg_completion=CompletionType.BRANCH` for tab-completion of branch names.

### Bug Fixes

- **Event loop exception guard**: `_dispatch_semantic_string` catches non-`ExitEventLoop` exceptions in overlay handlers, binding handlers, and child `_handle_event`, preventing a single panel callback from crashing the entire TUI.
- **`exec_external` decoupled via `ContextVar`**: `pigit.termui._session_context` provides `exec_external()` without requiring `Application` inheritance; `Session.__enter__/__exit__` correctly set/reset the context token.
- **`GitError` exception contract**: `checkout_branch` raises `GitError` instead of returning a string; callers use `try/except` with `show_toast` for user-facing errors.
- **`ItemSelector.previous` copy-paste fix**: removed the impossible `tmp >= len(self.content)` condition carried over from `next()`.

### Tests

- **`test_advanced_features` import path**: corrected `app_palette` → `app_command_palette`.

## 1.8.3 (2026-04-27)

### App

- **StatusPanel `C` key**: opens `$EDITOR` via `Application.exec_external` (TUI suspends/resumes around the editor session); checks for staged changes before launching.
- **Header branch name refresh**: `Signal[str]` drives branch name updates; `BranchPanel` writes the signal on successful checkout so the header updates immediately without waiting for a full re-render cycle.
- **`_PigitWidgets` dataclass**: consolidates 11 `Optional` widget fields in `PigitApplication.__init__` into a single dataclass with a `_w` property for non-null access.
- **Panel constructor cleanup**: removed unused `x`, `y`, `size`, `content`, `repo_path`, `repo_conf` parameters from `StatusPanel`, `BranchPanel`, and `CommitPanel`.
- **`CommitViewMode` enum**: replaces string `"list"` / `"river"` with `CommitViewMode.LIST` / `CommitViewMode.HEATMAP`.
- **`rel_time_cache`**: panel-owned `dict[str, str]` cache replaces mutation of `commit._rel_time` on model objects.
- **Inspector data objects**: `FileInfo`, `BranchInfo`, `CommitInfo` dataclasses replace the `isinstance` chain in inspector dispatch.
- **`ContributionGraph.render_into`**: public entry point so `CommitPanel` no longer calls the private `_render_surface` across classes.
- **`_draw_diff_line` helper**: deduplicates the per-line rendering logic shared between `DiffViewer._render_surface` (bordered) and `_render_surface_borderless`.
- **`app_palette` renamed to `app_command_palette`** with defensive checks.

### TermUI

- **Popup handler caching**: `Popup` pre-resolves `self` and child binding handlers in `__init__`, avoiding `resolve_key_handlers_merged` on every keypress.
- **`Application.BINDINGS` type annotation**: `Optional[BindingsList]` replaces untyped `= None`.
- **`BindingError` and `keys` exported**: added to `pigit.termui.__init__.__all__`.
- **`before_mouse_event` hook**: `AppEventLoop` exposes `before_mouse_event(event)` for subclass overrides.
- **Removed dead `LayoutEngine` Protocol**: no implementations existed; deleted from `_layout.py` and `_component_base.py`.
- **`Component.resize()` cleanup**: removed misleading `for child in self.children: child.resize(size)` propagation; layout containers (`Column`, `Row`, `TabView`) handle their own child sizing.
- **RGB migration completed**: all draw calls migrated to `*_rgb` methods; legacy ANSI draw methods removed from `Surface` and callers.
- **`describe_row` API**: `ItemSelector` subclasses declare row content declaratively as `(left, main, right)` segment tuples; base class handles truncation and alignment.
- **Color constants extracted**: `DEFAULT_BG`, `DEFAULT_FG`, etc. moved to `palette` module.
- **`fresh()` → `refresh()`**, `ActionLiteral` → `ActionEventType`.
- **ANSI sequence fix**: corrected 256-color and 16-color mode SGR sequences.

### Git

- **`load_status()` decoupled from rendering**: removed `max_width`, `ident`, `plain`, `icon` parameters; returns pure `File` data without width-dependent formatting.

### Renderer

- **Erase line tail on full-screen clear**: after `clear_screen()`, each written row is followed by `erase_line_to_end()` to prevent stale content from lingering on the right side when terminal width increases.

### Diff

- **CRLF handling**: strip `\r` before `expandtabs(8)` to prevent carriage returns from resetting the cursor mid-line.

### Docs

- **TermUI docstrings**: added to public classes and methods.
- **README picker note**: `_picker.py` documented as building-blocks only; `SearchableListPicker` not yet provided.
- **README section order**: Interaction moved before Commands.

### CI

- **Workflow filename**: `ci.yml` → `ci.yaml` to match PyPI trusted publisher requirements.

## 1.8.2 (2026-04-26)

### TermUI — Component model & layout

- **`Component.children` unified to `Sequence[Component]`**: removed dict-based children API and internal splits (`_child_list`, `_children`); `notify()` and `resize()` iterate `self.children` directly.
- **`LazyLoadMixin` inlined into `ItemSelector`**: activated via `lazy_load=True` parameter; deleted `_component_mixins.py`.
- **Local coordinates in `Column`/`Row`**: fixed double-offsetting bug where nested layouts applied global coordinates instead of local; `layout_flex` extracted to `_layout.py`.

### TermUI — Chrome & Header

- **`AppHeader` extracted to generic `Header`**: supports left/center/right slots and `on_refresh` callback for dynamic content assembly.
- **Badge system refactored**: `get_badge()` / `show_badge()` via `_overlay_context` (ContextVar-based); removed `on_badge` callback.
- **Dynamic footer help**: `AppFooter` collects entries from active panel's `get_help_entries()` instead of hard-coding.

### TermUI — Overlay system

- **`OverlayClientMixin` replaced by `_overlay_context`**: ContextVar-based overlay host lookup eliminates mixin MRO complexity.
- **`Popup.toggle()` calls `on_before_show()`**: opening a popup now triggers the child's `on_before_show()` hook before `show()`.

### App — Panel improvements

- **`StatusPanel` visual mode**: `v` toggles visual selection, `s` toggles scroll-select, `Space` toggles individual selection; batch actions (`a` stage, `d` discard, `i` ignore) operate on selected files.
- **`Repo` dependency injection**: `PigitApplication` and panels receive `Repo` via constructor, eliminating import-time side effects.
- **`relative_time` caching in `CommitPanel`**: `refresh()` computes once per commit into `commit._rel_time`; `relative_time()` decorated with `@lru_cache(maxsize=256)`.
- **Panel render comments**: `_render_surface` methods in `StatusPanel`, `BranchPanel`, `CommitPanel` now document layout intent and coordinate calculations.
- **`InputLine` block cursor**: physical cursor rendered as filled block; `set_content` scroll-reset bug fixed.
- **`StatusPanel` `C` key**: opens `$EDITOR` for git commit.

### TermUI — Error handling

- **`ComponentRoot.destroy()`**: bare `except Exception: pass` replaced with explicit `(RuntimeError, ValueError)` catch and error logging.
- **`AppEventLoop._dispatch_semantic_string()`**: key handler exceptions no longer swallow `ExitEventLoop`; explicit re-raise before generic catch.

### HelpPanel

- **Grouped display**: entries organized by panel title (`get_help_title()`); bold headers, blue keys (`THEME.accent_blue`), aligned descriptions.
- **`refresh_entries_from_source`**: renamed from `merge_help_entries_from_host_children`; auto-refreshes via `on_before_show()` before open.

### Fixes

- **`git show`**: omits empty `file_name` argument.
- **`TabView` panel switch**: clears renderer cache to prevent ghost content.

## 1.8.1 (2026-04-21)

### TermUI — InputLine enhancements & real cursor

- **InputLine widget**: added `on_submit`, `on_cancel`, `candidate_provider`, `set_prompt`, `set_candidate_provider`.
- **Inline Tab completion**: `Tab` opens candidate list, `Tab`/`Shift+Tab` navigates forward/backward, `↑`/`↓` also navigates; matched prefix stays normal, suffix shown dim (`\033[2m`); `Enter` confirms candidate without submitting; `Esc` restores original input.
- **Real terminal cursor**: `Renderer.set_cursor(row, col)` sets physical cursor position; components call it from `_render_surface`; cursor state cached to avoid redundant ANSI escapes per frame.
- **Magic key strings replaced**: `InputLine.on_key` uses constants from `keys.py` (`KEY_ENTER`, `KEY_ESC`, `KEY_TAB`, `KEY_SHIFT_TAB`, etc.).

### TermUI — Picker architecture: delete PickerAppMixin, eliminate sync blocking I/O

- **Deleted `PickerAppMixin`**: implicit-contract anti-pattern removed; filter/status logic inlined into `_CmdPickerApp` and `_RepoCdPickerApp`.
- **Parameter input via event loop**: `PickerMode.PARAM_INPUT` added; command arguments now collected through `InputLine` inside the event loop instead of synchronous blocking `read_line_with_completion` / `read_line_cancellable`.
- **Deleted `read_line_with_completion` / `read_line_cancellable`**: ~400 lines of raw cbreak line-editing code removed from `tty_io.py` — these were architecture leaks bypassing the event-driven model.
- **Deleted `ArgumentPrompter`** and its tests: no longer needed after param-input migration.
- **`_apply_filter` short-circuit**: skips rebuild when filter needle is unchanged.

### TermUI — Container consolidation & legacy cleanup

- **Deleted `LayoutContainer`**: zero production usage, superseded by `Column`.
- **`TabView` moved to `_component_layouts.py`**: it is a layout component, belongs with `Column`.
- **Deleted `_component_containers.py`**: empty after `LayoutContainer` removal and `TabView` migration.
- **`picker_layout.py` cleaned up**: removed `truncate_visual`, `normalize_filter_text`, `footer_status_line`, `filter_input_line` (no longer used by Component-based picker).

### TermUI — Efficiency fixes

- **Per-frame allocations**: eliminated redundant list slice allocations in `ItemSelector` and `LineTextBrowser`.
- **InputLine.set_value no-op guard**: avoids redundant callbacks when value is unchanged.
- **Cached renderer/terminal lookups**: `get_renderer_strict()` and `terminal_size()` cached in picker hot paths.

### Fixes

- **CI stability**: `test_loop_string_dispatch_calls_hooks_with_outcome` uses `RuntimeError("stop")` instead of `KeyboardInterrupt` to exit mock event loops (prevents pytest from interpreting it as external SIGINT).

## 1.8.0 (2026-04-18)

### TermUI — Rendering architecture overhaul

- **Surface / Cell intermediate layer**: declarative 2-D character buffer replaces direct ANSI emission; `Surface.draw_text`, `draw_row`, `draw_box`, `subsurface` APIs with CJK wide-character and ANSI SGR sequence support.
- **Incremental rendering**: `Renderer.render_surface()` uses row-level diff against previous frame, falling back to full clear on resize.
- **Box-drawing primitives**: `BoxFrame` in `frame_primitives.py` with `draw_onto` / `draw_content` APIs; replaces legacy `_build_bordered_frame`.
- **`_render_surface()` protocol**: all components migrated from `_render()` legacy path; `Popup`, `AlertDialogBody`, `HelpPanel`, `LineTextBrowser`, `ItemSelector`, `SearchableListPicker` now draw to `Surface`.

### TermUI — Component tree refactor

- **`Container` replaced by `TabView` and `LayoutContainer`**: `TabView` for tabbed component stacks (single active child); `LayoutContainer` for layout-engine driven multi-child rendering.
- **`Application` facade**: `PigitApplication(Application)` replaces `GitTuiRoot(OverlayHostMixin, Container)`; `Application.run()` composes `ComponentRoot` + `_ApplicationEventLoop`.
- **`ComponentRoot` + `LayerStack`**: `OverlayHostMixin` removed; overlay state managed by `LayerStack` with `LayerKind` (`NONE` / `MODAL` / `TOAST` / `SHEET`).
- **`Subsurface` layout**: components render into clipped proxies of parent `Surface` for nested layout regions.

### TermUI — Fixes

- **Alert drift**: `AlertDialogBody._needs_rebuild` invalidation prevents stale frame geometry after resize or message change.
- **StatusPanel refresh**: correct refresh after discarding the last file in a list.
- **Popup resize**: side-attached popups resized before render when geometry differs from terminal.
- **ANSI SGR in `Surface.draw_text`**: inline color sequences parsed and stored per-cell as `Cell.style`.

### Command system — complete rewrite (BREAKING)

- **`cmd_new` promoted to `cmd`**: the old `pigit cmd` system (`GitProxy`, `cmd_builtin`, `cmd_func`, `cmd_catalog`, `cmd_proxy`, `shell_mode`) has been completely removed. `pigit cmd` now maps directly to the new system powered by `GitCommandNew`.
- **`pigit/cmds/` package**: modular command definitions with decorators, models, registry, resolver, security validators, and config loader. Commands organized by domain: `branch.py`, `commit.py`, `history.py`, `index.py`, `merge.py`, `push_pull.py`, `rebase.py`, `remote.py`, `settings.py`, `submodule.py`, `working_tree.py`, `conflict.py`.
- **`--pick` as default**: `pigit cmd` with no arguments now launches the interactive picker; falls back to help when no TTY.
- **`pall` parallel command**: `pall` runs git commands in parallel across managed repos via `cmd_new`.
- **Shell completion updated**: bash/zsh/fish completion scripts now serve `cmd_new` commands under the `cmd` namespace.
- **`g` shortcut preserved**: continues to work since it prefixes `cmd`, which now resolves to the new system.
- **Legacy backup**: `cmd_builtin.py` backed up to `docs/cmd_builtin_legacy.py` for reference.
- **Git command picker UX**: `SearchableListPicker` with real-time preview pane, tab-completion via `read_line_with_completion`, and alt-screen handoff so picked command output is visible.
- **Internal decoupling**: `tty_io` decoupled from `cmdparse`; picker internals split into `_picker_prompt.py`, `_picker_sorter.py`, `_completion.py`.

### Tests

- Expanded termui test coverage: `Toast`, `Sheet`, `HelpPanel`, `Popup`, `AlertDialogBody`, `LayerStack`, `KeyboardInput`, `ComponentRoot` pop-layer lifecycle.
- **Removed completion script generation** from docs (shell completion scripts managed separately).

## 1.7.8 (2026-04-03)

### TermUI — overlay and bindings

- **Single modal slot**: `OverlayHostMixin` + `OverlayKind` / `OverlayDispatchResult` / `OverlaySurface`; `OverlayController` forwards keys to the active shell’s `dispatch_overlay_key` (exceptions → `CLOSED_AFTER_ERROR` + host cleanup).
- **Event loop**: `window resize` before overlay routing; while `has_overlay_open()`, keys use `try_dispatch_overlay` only (main tree does not receive them). `KeyDispatchOutcome` includes `overlay_explicit`, `overlay_implicit`, `overlay_drop`, `overlay_closed_after_error`. `_loop` split into `_dispatch_semantic_string`, `_dispatch_while_overlay_open`, `_dispatch_while_overlay_closed`.
- **`Popup`**: optional `session_owner`; `_resolved_overlay_host()` uses `nearest_overlay_host()` or treats the owner as host when it already has overlay APIs. No constructor restriction on child type; implicit toggle keys come from the child class’s `TOGGLE_HELP_SEMANTIC_KEYS`. Renderer for side-attached shells is applied in `_render` via `_sync_renderer_from_session_owner` (walk `session_owner` / `parent`); removed `AppEventLoop._bind_side_overlay_components`.
- **`AlertDialog`**: same `session_owner` pattern via base `Popup`; ESC / confirm flow unchanged at the API level.
- **`HelpPanel`**: `refresh_entries_from_source` aggregates `get_help_entries()` from `entries_source.children` into the panel (replaces the old `populate_*` name).
- **Bindings**: `bind_keys` + class `BINDINGS` merged in `resolve_key_handlers_merged` / `list_bindings`; duplicate keys to the same target deduped; conflicts raise `BindingError` with `semantic_key`, `first_target`, `second_target`, `owner_class_name`.
- **Text**: `sanitize_for_display` for safe overlay strings.
- **Exports** (`pigit.termui.__all__`): among others `AlertDialog`, `Popup`, `HelpPanel`, `HelpEntry`, `OverlayHostMixin`, `OverlayKind`, `OverlayDispatchResult`, `OverlaySurface`, `bind_keys`, `BindingError`, `list_bindings`, `sanitize_for_display`.

### Git TUI (`pigit.app`)

- **`GitTuiRoot`**: one overlay slot (help `Popup` vs `AlertDialog`); `?` toggles help; help rows refreshed via `HelpPanel.refresh_entries_from_source` before open.
- **`StatusPanel._check_via_alert`**: after confirm, **`refresh()`** reloads status and the cursor is clamped so the list updates on the same frame as the closing dialog (no extra keypress).

## 1.7.7 (2026-03-29)

- **Breaking (CLI pickers / termui)**
  - Removed `pigit.termui.scenes` (and `run_list_picker`). Full-screen pickers use **`AppEventLoop`** + **`SearchableListPicker`** only.
  - **Types / helpers**: `PickerRow`, `PICK_EXIT_CTRL_C`, `apply_picker_filter` → `from pigit.termui.component_list_picker import …`
  - **`repo cd --pick` glue** → `pigit.git.repo_cd_picker` (`run_repo_cd_picker`, `EMPTY_MANAGED_REPOS_MSG`, `REPO_CD_NO_TTY_MSG`, …).
  - **`pigit cmd --pick` / `repo cd --pick`**: require a real TTY; no headless or fake-input test harness in product code.
- **Migration (copy-paste)**:
  ```text
  # Old (removed)
  from pigit.termui.scenes.list_picker import run_list_picker, PickerRow

  # New — data / component
  from pigit.termui.component_list_picker import PickerRow, PICK_EXIT_CTRL_C, apply_picker_filter

  # New — product entrypoints stay in git
  from pigit.git.cmd_picker import run_command_picker
  from pigit.git.repo_cd_picker import run_repo_cd_picker, EMPTY_MANAGED_REPOS_MSG
  ```
- **Internal**: `pigit.termui.picker_event_loop.PickerAppEventLoop` (pickers run only inside a real TTY `Session`), `Renderer.draw_absolute_row` / `erase_line_to_end`; `ExitEventLoop` carries optional `exit_code` / `result_message`; `AppEventLoop.quit(..., exit_code=, result_message=)`.

## 1.7.6 (2026-03-29)

- **Internal TUI** (`docs/technical_termui_event_loop_components_phase1.md`): Centralized `BINDINGS` resolution in `pigit.termui.bindings.resolve_key_handlers`; `Component` and `AppEventLoop` store `Dict[str, Callable]` as `_key_handlers` (construction-time errors for bad string targets). `ItemSelector` no longer duplicates a separate `event_map`.
- **Internal**: Removed process-wide `NAME` uniqueness (`_NamespaceComp`); `NAME` remains required and non-empty; routing stays keyed by `Container.children` and `emit("goto", ...)`.
- **`AppEventLoop`**: Optional hooks `before_dispatch_key` / `after_dispatch_key` with `KeyDispatchOutcome` (`"binding"` | `"resize"` | `"child"`) on string-key dispatch only; default `PanelContainer` behavior unchanged (`Container.key_routing="child_first"`).
- **Tests**: `tests/tui/test_termui_bindings.py`; extended event-loop and container coverage for hooks, callable bindings, and `key_routing`.

## 1.7.5 (2026-03-29)

- **Breaking (internal TUI)**: `AppEventLoop` always runs inside `pigit.termui.session.Session` with `TermuiInputBridge` + `KeyboardInput` when `input_handle` is omitted. Removed `use_termui_keyboard`, default `PosixInput` / `pigit.termui.legacy_input`, and the non-session `renderer_for_stdout` path.
- **Internal**: `AppEventLoop._run_impl` uses `logging` (`PIGIT.pigit.termui.event_loop`): `ExitEventLoop` → debug line; `KeyboardInterrupt` / `EOFError` silent after `stop()`; other exceptions → `logging.exception` (no stdout traceback prints).
- **Extensions**: Custom `InputTerminal` implementations may still emit legacy 4-tuple mouse events; they are ignored via `pigit.termui.keys.is_mouse_event` (same shape as before). String semantic keys remain the supported contract for `KeyboardInput` / `TermuiInputBridge`.
- **Other**: `Renderer` is only constructed from a live `Session`; `TermuiInputBridge.set_input_timeouts` rejects non-finite or negative values. List picker test hook mapping renamed to `_raw_tty_char_to_semantic`.

## 1.7.4 (2026-03-27)

- **Breaking**: Removed legacy packages `pigit.tui` and `pigit.interactive`. Terminal UI lives under `pigit.termui` only.
- **Migration**:
  - `pigit.tui.components` / `pigit.tui.event_loop` → `pigit.termui.components` / `pigit.termui.event_loop` (class `EventLoop` renamed to `AppEventLoop`).
  - `pigit.tui.utils` (`get_width`, `plain`) → `pigit.termui.text` (same symbols).
  - `pigit.tui.input` → `pigit.termui.legacy_input` (`PosixInput` and helpers).
  - `pigit.interactive.list_picker` / `repo_cd` / layout / tty helpers → `pigit.termui.scenes.list_picker`, `pigit.termui.scenes.repo_cd`, `pigit.termui.picker_layout`, `pigit.termui.tty_io`.
- **Implementation**: `Renderer.draw_panel` replaces static `Render.draw`; `AppEventLoop` injects a single `Renderer` into the component tree. `get_width` / `plain` are implemented in `termui/text.py` + `termui/wcwidth_table.py`.

## 1.7.3 (2026-03-26)
- **Unified term UI (`pigit.termui`)**: Session, Renderer, KeyboardInput (semantic keys), list picker on `Session` + `KeyboardInput`, optional `--pick-alt-screen` for `pigit cmd` / `pigit repo cd --pick`.
- **Main TUI (`App`)**: `EventLoop(..., use_termui_keyboard=True)` runs inside `pigit.termui.session.Session` with `TermuiInputBridge` over `KeyboardInput` (legacy `PosixInput` remains the default for `EventLoop` when the flag is off).
- **Deprecation (P3)**: Importing `pigit.interactive` emits a one-time `DeprecationWarning` directing new code to `pigit.termui`. The `pigit.tui` package is documented as legacy (no runtime warning) because `pigit.termui.text` still imports `pigit.tui.utils` for a single `get_width` / `plain` implementation.

## 1.7.2 (2026-03-23)
- Update `.gitignore` template

## 1.7.1 (2026-03-23)
- Rename git modules: `_cmd_func.py` → `cmd_func.py`, `proxy.py` → `cmd_proxy.py`, `_cmds.py` → `cmd_builtin.py` (public re-exports in `pigit.git` unchanged).
- **CLI (`pigit cmd`) discoverability**: `-l`/`--list` replaces the old full-table `-s`; `-s`/`--search <query>` adds case-insensitive substring search; `-p`/`--pick` adds a built-in TTY picker (j/k, Enter, `/` filter, q); `-t`/`--type` merges “list types” and “list by type” (`-t` vs `-t Branch`). Friendly errors and `-h` epilog point to the new flags. `GitProxy` lists/search/pick share `CommandEntry` via `cmd_catalog.py`; `extra_cmds` rows show an `[extra]` prefix in list/search/pick output.
- Optimize load_status cache: use stat tuple of .git/index/HEAD/MERGE_HEAD as signature (no watchdog/FSEvents), merge repeated calls via _LOAD_STATUS_CACHE_TTL (0.3s), skip cache for worktree with gitdir:.
- Improve add_repos performance: change exist_paths to set (O(1) member detection), keep confirm_repo call for each path.
- TuiHandler takes over first-launch guidance + App().run(), preprocess() handles Windows unsupported branches; RepoCommandHandler has no inheritance with BaseHandler; top-level pigit still processes report/config/count/complete parameters.
- Adjust ExecutorFactory: LocalExecutor uses multiple inheritance (Executor + ExecutorStrategy) to keep exec/exec_parallel behavior consistent; add reset() fixture for ExecutorFactory in unit tests to avoid singleton pollution.
- Optimize PigitContext: keep ExecutorFactory.get() logic unchanged to avoid test semantic conflicts; Config remains Singleton; repo_handler is retained as compatible alias for app_ctx.repo.
- Evolve multi-repo parallelism: ManagedRepos uses exec_parallel(..., max_concurrent=…) based on asyncio; map PIGIT_REPO_MAX_WORKERS to max_concurrent (default 4).
- Optimize streaming log & ItemSelector viewport: parse git log incrementally via exec_stream; fix j/k navigation error in BranchPanel/CommitPanel by using set_content.
- Implement progressive TUI: GitPanelLazyResizeMixin optimizes Component.resize logic; PanelContainer.switch_child ensures tab data refresh; no background thread async git to avoid rendering race.

## v1.7.0 (2024-05-15)
- Fix command completion generate multi key.
- Use `eval "$(pigit --complete zsh)"` to take effect manually command completion.
- Adjust generate way of '.gitignore', and more faster.
- Improve code counter and improve operating speed.
- Refactor the structure of TUI model, support better experience.
- Add `repo cd` to quickly jump to managed repos.

## v1.6.1 (2023-01-25)
- Use config control file icon in tui mode.

## v1.6.0 (2022-08-22)
- Show file icon in tui mode.
- Use new dependencies -- `plenty`(render).
- Independent render part, which is convenient for maintenance.

## v1.5.2 (2022-04-27)
- Fix parameter typing of Python3.8
- Fix `repo ll` command  error, when has invalid repo path.
- Fix tui mode bugs when removing all new files or modifications from the bottom up.
- Improve the shell mode.
- Improve some inner util methods.
- Improve `Console.echo()` support object.
- Improve the way of custom command, remove `type` field.
- Add `cmdparse` that support building the command line through the decorator.
- Add `gitlib` that package the operating instructions for Git.

## v1.5.1 (2022-03-24)
- Support using pigit like a normal third-module.
- Fixed bug of tui mode.
- Improve pigit code structure.
- Improve code counter output.
- New rendering module.
- Update style, support background color.
- Beautify the repo option output.

## v1.5.0 (2022-02-26)
- Refactor code, split sub-command of usage.
- Refactor shell completion.
- Refactor args parser.
- Feat function, add `repo` option.
- Feat function, add `open` option.
- Fix color error of print original git command.
- Fix some logic bug of TUI.
- Fix can't process chinese error of TUI.
- Update config.
- Remove useless function: `tomato`.

## v1.3.6 (2022-02-10)
- Console add `--alias` command.
- Interaction mode add ignore fuc.
- Add new short git command about submodule.
- Update log info more clear.

## v1.3.5 (2022-01-15)
- Refactor part of code.
- Fix `ue` command about setting global user and email.
- Fix `--create-config` command when don't have config.

## v1.3.4 (2021-12-26)
- Split TUI module.
- Refactor interaction mode.
- Add branch model of interaction.

## v1.3.3 (2021-11-05)
- Optimize CodeCounter.
- Refactor shell completion.
- Dep update to Python3.8
- Optimize shell mode.

## v1.3.2 (2021-10-11)
- Fix table class for chinese and color.
- Fix get repo path error when in submodule repo.
- Adjust the command line parameters, `pigit -h` to view.
- Simple interactive interface support commit part.

## v1.3.1 (2021-09-28)
- Add new git short command (submodule).
- Add new config option.
- Add table class.
- Improve code logic and format.

## v1.3.0 (2021-09-09)
- Not continue support Python2.
- Update config and config template.
- Improve code counter running speed.
- Code counter output support icon.
- Fix color command error.
- Add simple shell mode.

## v1.0.9 (2021-08-24)
- Update owned commands.
- Supported interaction of windows.
- Improved CodeCounter.
- Fixed some error.
- Update documents.

## v1.0.8 (2021-08-18)
- Split package.
- Fixed shell completion.
- Allow setting custom cmds.

## v1.0.7 (2021-08-11)
- Refactor config.
- Compat with python2 of interactive mode.
- Add delete and editor in interactive.

## v1.0.6 (2021-08-08)
- Rename project, pygittools -> pigit
- Added configuration.
- Added interactive file tree operation.
- Allowed some command combined use, like: `-if`.
- Optimized ignore matching algorithm of CodeCounter.
- Increase the output mode of CodeCounter. [table, simple]
- Refactor Git command processor.
- Refactor Completion, support fish shell.
- Fix emoji error on windows.

## v1.0.4 (2021-08-04)
- Optimized recommendation algorithm.
- Optimize the output of CodeCounter results.
- Repair CodeCounter matching rule.
- Compatible with windows.

## v1.0.3 (2021-08-02)
- Support code statistics.
- Support command correction.
- Update completion.

## v1.0.2 (2021-07-30)
- Add debug mode.
- Update completion function.
- Support create `.gitignore` template according to given type.
- Show runtime.
- Improve print, more color and beautiful.
- Fix color compatibility with python2.

## v1.0.1 (2021-07-28)
- Support quick view of GIT config
- Support to display warehouse information
- Improve description.
- Improve help message.

## v1.0.0 (2021-07-20)
- Fist release.
- Support Python2.7 and Python3.
- Can use short git command.
- Support shell complete.
- Auto check git version.
