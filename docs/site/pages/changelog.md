# Changelog

Release notes for **2.0.0 and later**. Older versions are in the repository
[CHANGELOG.md](https://github.com/zlj-zz/pigit/blob/main/CHANGELOG.md).

## 2.5.1 (2026-08-30)

### Features

- **Brand-color sheet edge rule**: every sheet (repo/worktree switcher, command palette, commit, rebase, log ref, bisect, recent, inspector, welcome) paints its facing-edge rule with the theme's brand accent, so pickers and drawers read as part of the product chrome. The ` · title · ` decoration is now a single app-side `sheet_core()` helper.

### Bug Fixes

- **Observe treats the Status tab as one unit**: the Status and Stash panels refresh together while the Status tab is active, so stash create/pop operations appear immediately instead of being ignored as a non-focused presentation leaf (fixes #79).

### Improvements

- **Word-diff highlights stand out**: intra-line additions/deletions render with italic plus a brighter background so they read at a glance against the base diff tint.
- README restyled with emoji section headers, hero badges, and freshly recorded interaction demos.

### Refactors

- **Sheet title becomes a verbatim slot**: the framework `Sheet` paints a caller-composed center slot (`title_core`) instead of wrapping ` · title · ` itself, keeping the format decision in the app layer.
- **ext/ slimming**: dropped the hand-rolled `Singleton` metaclass for a module-level `get_config()`, shrank `time_it` to a plain elapsed counter, deleted the dead `_do_*` delegates, and turned `ExecutorFactory` into module-level functions.
- Resolved pyright diagnostics across `PigitApplication` and the `Application` base (`min_terminal_size`, generic `_resolve_index`, `get_help_groups` typing).

## 2.5.0 (2026-08-29)

### Features

- **Command palette parameter completion**: `;` lists parameterized commands (checkout/merge/stage/gitignore) whose branch/file arguments complete from in-memory lists; typing a command + space switches the list to arg candidates, and Tab fills the selected candidate into the input.
- **Undo for merge/rebase/cherry-pick**: `u`/`U` now reverse a completed merge, rebase, or cherry-pick by resetting to the recorded pre-operation HEAD; every undo asks for confirmation showing what it reverses and the git command it runs, and refuses a hard reset while the worktree has uncommitted changes.
- **Nerd Font detection + fallback**: `icons: auto|on|off` replaces `file_icons`; `auto` enables glyphs on known Nerd Font terminals (kitty/WezTerm/Alacritty/Ghostty) and otherwise falls back to 1-cell plain symbols (also fixing the misalignment when icons were disabled). The generated config template emits the quoted `icons = "auto"` key with a regression test that parses the whole template.

### Improvements

- Command palette hint shows Tab completion; `u`/`U`/`@` help text reflects confirmation, undo scope, and in-place repo/worktree switching; `;` is no longer in the footer (still in Help and the Welcome sheet).

### Refactors

- Session history's reverse dispatchers become a single `_ReverseSpec(exec, describe)` registry; icon rendering converges on `resolve_icon` with the dir glyph moved into `ext.utils`.

## 2.4.0 (2026-08-29)

### Features

- **Multi-repo TUI**: clickable Header repo slot opens the switcher sheet; selecting a repo swaps the live session in place (RepoSession abstraction, token-guarded async, undo isolation per repo).
- **Worktree TUI**: `w` in the repo switcher lists `git worktree` trees and switches to one in place by reusing the repo-switch machinery; `+` adds a linked worktree (branch defaults to HEAD), `-` removes with a dirty `--force` confirm.
- **Bisect TUI**: `B` opens a status sheet showing the current commit, good/bad refs, and remaining steps; `s` starts (`good [bad]`, bad defaults to HEAD), `g`/`b` mark the current commit, `r` resets. Bisect and sequencers are mutually exclusive through a single gate (merge/rebase/cherry-pick/branch-checkout/repo-switch).
- **First-run Welcome sheet**: panel map + core keys, pointing at `?` for the full binding catalog.
- **Executable Help browser**: binding rows are runnable; click selects, double-click runs the bound action.
- **Anchored panel popup**: clicking a Header tab slot opens a picker anchored to the slot (dismiss on outside press or `esc`).
- **Push upstream confirm**: pushing a branch with no tracking ref asks before setting it as upstream.

### Bug Fixes

- Anchored picker no longer closes on the opening click's release — only an outside press dismisses it.
- Side preview stops reloading when the selection is unchanged.
- Sheets stay within the header/footer chrome: the footer now shows the open sheet's key hints instead of being covered, and the rebase sheet no longer duplicates them in its own footer.
- Welcome / Inspector top sheets no longer cover the header.

### Refactors

- Extract `RepoSession`; panel ViewModels become retargetable for in-place repo switches.
- Consolidate toast/sheet chrome reservation into `bottom_chrome_pad` / `top_chrome_pad`, sourced from the `HEADER_HEIGHT` / `FOOTER_HEIGHT` constants.

## 2.3.1 (2026-08-27)

### Features

- **List chrome**: OptionList owns the cursor column (`CURSOR` / `CURSOR_ACCENT`); Status / Branch / Stash use a `SectionRule` (accent when focused).
- **Header**: `*` current-branch marker (green clean / amber dirty) with live dirty updates from observe digests; compact upstream arrows.
- **Diff hunk headers**: accent-tinted row fill; adaptive line gutter (drops below narrow widths).
- **Toasts**: dock above the footer with stable card sizing; neutral toasts use the brand accent border.
- **Lazy panels**: skeleton loading bars; Status / Stash empty states with real next-step hints.
- **Status file icons**: Nerd Font prefixes beside names; opt out via config or `PIGIT_ICONS=0`.
- **Commit selection / contribution report**: full selected-row background; current-week heatmap tint; unpushed HEAD stays yellow; author line colors and legend aligned with heatmap Less.

### Bug Fixes

- Diff hunk headers keep horizontal scroll / truncation; line numbers clip to the gutter instead of overflowing into `+/-`.
- Loading / empty: force-notify when a refresh completes with an unchanged empty list so skeletons clear on clean trees.
- Header dirty dot stays fresh off the Status tab; pure worktree batches refresh dirty state without extra git subprocesses.
- Multi-line toasts keep trailing hint lines (truncate from the head).
- Diff horizontal scroll budget uses the adaptive gutter width.

### Improvements

- Named constants for hunk blend, skeleton widths, and footer height (toast pad tracks footer).
- Shared `GRAPH_PAD` keeps expanded commit rails aligned under the cursor mark.

## 2.3.0 (2026-08-26)

### Bug Fixes

- **Diff scroll / hunk jump**: DiffViewer owns `_lines` / `_line_i` instead of a nested TextBrowser scroll bag, so `]` / `[` near EOF still land on late hunks and path badge / file-history (`v`) resolve the correct file.

### Refactors

- **LineTextBrowser → TextBrowser**; **BorderedBrowser → BorderedTextBrowser** (widgets package + callers).
- TextBrowser exposes `lines` / clamped `scroll_i` / `replace_lines`; resize no longer permanently clamps deep scroll across viewport shrink/restore.
- Test layout: consolidate duplicated Column/Row and scattered cases; CI uploads coverage to Codecov.

## 2.2.0 (2026-08-26)

### Features

- **Diff as body detail**: DiffViewer sits in an exclusive body layer over Status / Branch / Commit (warm show/hide) instead of a fourth TabView page.
- **OptionList chrome bands**: optional header/footer slots with fitted band heights; Commit report migrates onto the list chrome.
- **CommitEditor widgets**: public `Label`, `StaticList`, and `ShortcutHints` replace private staged/hint helpers.
- **Panel fg hierarchy**: dim inactive presentation via `presentation_fg` on steal/focus without painting row backgrounds.
- **DiffContent**: parse/install path extracted from DiffViewer so content swaps stay atomic.

### Improvements

- **Mount vs visibility**: `ExclusiveView` (warm) / `TabView` (cold); `activate` → `mount`; paint gated by exclusive visible child; Diff pauses background work on hide.
- **Surface unify**: single drawing type (no separate subsurface type).
- **Component `paint`**: draw hook renamed from `draw` for consistency.
- **Theme**: contribution / graph colors route through `PigitTheme`.
- **App orchestration**: panel navigation and observe deps extracted from `PigitApplication`.

### Refactors

- **ItemList → OptionList** (module, widgets, panels, tests).
- Body tree typing: required attrs set in `build_root`; pyright-clean `pigit` package (`TAB_NAME` + `tab_name` property, typed browsers / ObserveDeps).

### Bug Fixes

- Product navigation tolerates an unbuilt body (tests / early paths) without crashing on missing `_body_view`.

## 2.1.1 (2026-08-22)

### Features

- **Command palette**: open-with catalog (`PaletteItem` id + description), context-aware sequencer actions, scroll cues, and sheet height from terminal budget.
- **Sheet height protocol**: children may implement `preferred_sheet_height`; `show_sheet` resolves and clamps (`max_fraction` when height is omitted).
- **Sheet edge chrome**: facing edge is a full-width `─` rule that can embed ` · title · ` (align left/center/right, default right).
- **Commit editor**: shortcut hint strip; staged list no longer paints a solid panel fill.
- Empty DiffViewer still draws box chrome.

### Bug Fixes

- Log-ref / palette tests stay aligned with height and title APIs (no stale `terminal_size` patches).
- Palette list slots use the same root height source as sheet resolution.

### Docs

- Refresh the architecture map in `CLAUDE.md`.

## 2.1.0 (2026-08-21)

### Features

- **Global Push / Pull (`P` / `F`)**: non-interactive `git push` / `git pull` on the current branch via `AsyncTask`, with a centered animated spinner (INFO chrome, min width), busy guard, and shared path with the command palette.
- **Alert dialogs by `FeedbackKind`**: replace `destructive=` with `kind=`; irreversible confirms use `ERROR`, caution confirms use `WARNING`, with theme chrome and Segment-styled OK/Cancel.
- **Help**: show bindings for the active panel, then Global only.

### Bug Fixes

- Header ahead/behind (`↑` / `↓`) sits next to the branch name instead of the centered Header slot.
- Merge-workflow push always settles checkout-back after the async push attempt (success or failure).
- Pull conflicts persist `mode=pull` merge state, surface git detail in the toast, and resume via `continue-merge` without branch checkout-back.
- Network sync `work()` never raises into `AsyncTask` (non-`GitError` becomes a failed outcome so busy/spinner clear).

### Improvements

- `GitApi.push()` with `GIT_TERMINAL_PROMPT=0` (same non-interactive env on `pull`).
- `ToastPosition.CENTER` and spinning `show_spinner(..., position=)`.

## 2.0.0 (2026-08-20)

### Breaking Changes

- **Python 3.11+ required** (dropped 3.10). Install with a 3.11+ interpreter (Ubuntu 22.04 system Python is 3.10).
- **`app.auto_refresh_interval` removed**: replaced by repo observation (`app.repo_observe`, `app.observe_worktree`). Legacy keys are ignored with a warning.
- **UI config under `[app]`**: nest former top-level TUI / keybinding tables under `[app]` (legacy sections warn and are ignored).

### Features

- **Repo observation**: StatMtime-based watch of `.git` metadata and (optionally) the worktree; panels refresh on real changes instead of a blind timer.
- **Inspector (`I`)**: frozen top-edge snapshot of the current selection (async load).
- **Cherry-pick (`c`)** from the Commit panel onto current HEAD.
- **Log another ref (`o`)** from Branch / Commit to browse that ref's history.
- **Stash message prompt** on Status `s`; apply without dropping; confirm before drop.
- **Status `A` stages all**; amend moved to `m`.
- **Status tree toggle** with `Ctrl+t`.
- **Header** colors the repo name and current branch.
- **Commit contribution-graph** report strip.
- **termui Theme**: semantic color roles; widgets stop treating `palette.DEFAULT_*` as UI roles.
- **termui widgets**: Footer, CommandPalette, ItemList `/` search, SplitPane / BorderedBrowser, Sheet footer chrome, primitives (word-diff, gutter, calendar layout).
- **Grouped help** and tab metadata; `min_terminal_size` for Pigit.

### Bug Fixes

- Sheet open/dismiss syncs focus so the body dims on the first frame.
- Overlay `InputLine` releases focus grab on Enter submit (picker `/` filter).
- Observe: dir mtime discovers new refs/files; porcelain digest wakes Status on clean→Modified; metadata poll bounded.
- Status preview loads diffs by path (not stale `source_idx`).
- Commit panel clears refs cache before row rebuild; graph rows publish before items on load.
- Inspector snapshot build no longer blocks the UI thread.
- Cmd Tab completion no longer inherits branch completers incorrectly.

### Refactors / Tests

- Slimmer termui public façade and `primitives` package; app import ratchets.
- App-layer tests live under `tests/app/`.

---

For **1.x and earlier**, see
[CHANGELOG.md on GitHub](https://github.com/zlj-zz/pigit/blob/main/CHANGELOG.md).
