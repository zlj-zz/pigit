# Changelog of pigit

## 1.7.5 (2026-03-29)

- **Breaking (internal TUI)**: `AppEventLoop` always runs inside `pigit.termui.session.Session` with `TermuiInputBridge` + `KeyboardInput` when `input_handle` is omitted. Removed `use_termui_keyboard`, default `PosixInput` / `pigit.termui.legacy_input`, and the non-session `renderer_for_stdout` path.
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
