# Changelog

Release notes for **2.0.0 and later**. Older versions are in the repository
[CHANGELOG.md](https://github.com/zlj-zz/pigit/blob/main/CHANGELOG.md).

## 2.12.0 (2026-10-27)

### Features

- **A scrollbar rides the frame's right border.** A long diff, help page or preview said nothing about where you were: the only hint in the app was the diff's horizontal `← 42% →` on its bottom border, and vertical scrolling had none. `BoxFrame` owns the border cells every framed component draws, so the bar lives there — the thumb replaces `▐` cells on the right border column, the track is the border's own `│`, and nothing is added: no column, no background, no new widget. The thumb is proportional and the offset is clamped before the division, because a viewport that shrank after scrolling can leave the recorded offset past the end. It follows the frame's own foreground rather than a fixed tone — borders differ, accent on the active diff and dim on an inactive one and primary in Help, and one fixed colour sat darker than a primary border. Content that fits leaves the border untouched.
- **The confirmation dialog reports its position the same way.** It said `Confirm (3-7 of 12)` in the title — text, where every other framed view now has a bar. The title is `Confirm` again and the thumb on the right border carries the position.
- **Every page opens with a section rule, and the rule counts.** The rule is the only region separator this design has — no borders, no filled panel backgrounds — so a page without one started flush against the top edge and read as if it came from another app. Status, Stash and Branch wore it; Commit and Graph did not, and both do now. The label also moved to the left, where the content it names begins, and a muted counter follows it: `── Status · 2/24 ─────`. The denominator is the number of items, not rendered rows — an expanded commit puts several rows behind one item.
- **The header says which page of how many.** The tab slot read `Status [1]`, which named the key but not how many pages there were, so the number keys read as arbitrary digits. It reads `Status [1/5]` now, and the total comes from the panel ring rather than a literal, so adding a page cannot leave the counter behind. A view with no digit key, the diff detail, still renders just its name.

### Improvements

- **The side preview takes the width it can use.** The split gave the list a fixed share of the terminal — 35%, then 40% — so a wider terminal mostly widened the list, where past a point the extra columns are blank: a row is a path plus a status label, while the diff next to it can always use more. The preview starts at 130 columns now, a 60-column list plus a 70-column diff, the narrowest one still worth reading; the list holds 60 and gains one column for every five the terminal gains after 150, up to 120; everything else goes to the diff, which therefore ends up the wider pane. The width is a policy of columns rather than of share: a ratio that tapers as the terminal grows peaks around 275 columns and then falls, so widening the terminal would narrow the list.

### Bug Fixes

- **Column widths come from the interpreter's Unicode data.** The 38-range table was a frozen 2010 snapshot: 22,117 code points disagreed with the Unicode version Python ships, counting emoji as one column and most combining marks as one, so a row containing them shifted everything after it. Widths are asked of `unicodedata` now — nonspacing and enclosing marks zero, East Asian Wide/Fullwidth two, the rest one. The CJK unified block is unchanged; compatibility ideographs and the supplementary blocks move to two columns.
- **Emoji are measured as the glyph a terminal draws.** Composed sequences were measured as their parts: a woman technologist came out five columns, a family of three eight, a thumbs-up with a skin tone four, when each is a single two-column glyph. A U+FE0F selector widens the base UTS #51 lists, a two-column character after ZWJ joins the glyph before the joiner, and a skin-tone modifier folds into what it modifies. Invisible format characters — ZWSP, ZWNJ, ZWJ, BOM, the bidi controls — are zero-width, while the fourteen `Cf` characters that do draw stay one column. The alert dialog's wrapper compared one character at a time, where a selector can never be seen, and was the one place that could still paint over its own border.
- **The diff offset stays inside its content.** The setter clamped only the lower bound, and paint starts at the offset, so a value at or past the last line rendered an empty screen — reachable from the offset cache and the File History snapshot restore, not only from the public setter.
- **A framed browser is sized to the surface it paints.** `paint` recomputed the frame from the surface it was handed but left the inner browser at the size of its last `resize`, and the child draws from its own size: a narrower surface painted content over the right border, and a taller one drew only the old viewport rows while the surface had room.
- **A file header stays whole before the syntax tokens land.** The renderer's fallback strips a diff prefix from any line starting with `+`, `-` or a space, so a `---`/`+++` header was painted as `-- a/x` and `++ b/x` and corrected itself only once tokenization finished. On a large diff that is long enough to see.
- **The panel picker's key column lines up.** The key hint followed the name directly, so the bracket column followed the name's length: Stash and Graph, at five characters, sat one column left of Status, Branch and Commit at six.
- **The narrow-preview toast names the route that still works.** Below the preview threshold `Ctrl+P` said the preview needs more columns and nothing else — a dead end on the 80-column terminal where this most often happens, even though the content is one keypress away. It says Enter opens the full diff from Status and Stash, and that the Graph tab carries the log for Branch. Commit and Graph have no side preview at any size, so they no longer report a width problem for a key their panel does not bind.

## 2.11.0 (2026-10-13)

### Features

- **Run the commit editor's shortcuts by clicking them.** `Ctrl+Enter` only works where the terminal volunteers an extended keyboard sequence, and pigit parses those without ever asking for them: kitty and wezterm send one, herdr sends a bare `\r`, which is the byte a plain Enter sends. The status bar went on advertising a key that could not arrive. Its `Ctrl+Enter commit`, `Tab body` and `Esc cancel` are mouse targets now — the label already names the action, and a click needs no protocol. A press that moved is a drag, not a click, so sliding across the strip cannot commit on the way to cancel.
- **Check out a remote branch by creating the local one.** `c` refused a remote-tracking row outright. It now creates the branch the row implies, tracking it, and switches — the everyday `git checkout <name>` behaviour the CLI already had and the TUI did not. The remote ref goes in whole rather than as the name it shortens to, because two remotes can carry the same branch name. A local namesake is a warning rather than an error: there is nothing to create and nothing went wrong.
- **Every declared action is reachable from the command palette by name.** The palette was a hand-written list of 15 ids in a vocabulary of its own, so not one of the 152 declared actions could be found by typing its name. It is derived from the bindings now — the same rows the Help panel reads — and each row prints the description rather than the id. Fetch, continue-merge and the six sequencer controls existed only in the palette and are keyless bindings now, and each refuses when no such sequencer is running instead of running `git` and surfacing its error.
- **A panel whose load failed says so until it succeeds.** The failure reached only a three-second toast, so the panel went on claiming it was loading — on a first load, its skeleton was drawn for good — and with rows already loaded every key acted on a list that was quietly out of date. The header wears the error glyph now until a load succeeds, and a panel with nothing to show explains why in place of the skeleton. The toast stays: it says *this just happened*, where the mark says *this is still true* — and for a load nobody asked for, the toast is the only thing that reaches someone looking at another tab.

### Improvements

- **Stash is its own page.** It was a band pinned under Status, so the five panels the number keys and `Tab` cycled through were not the four pages that existed: pressing the Stash key moved the focus without ever changing the page. The five ring entries and the five pages are the same five things now, and Status gets back the rows the band held.
- **The cursor row is marked the same way on every list panel.** Commit banded its cursor row; Status, Stash and Branch marked theirs with an accent bar on the cursor column alone, which on a wide screen put the mark and the row it belonged to a hundred columns apart. All four wear the same band, which dims rather than disappears while a sheet is over the panel.
- **The darker surfaces are further apart.** The panel background, the hover row and the active row sat 6–12 values apart and read as a single tone; each rung is now about 10 from the next — the smallest step that still separates on a dark terminal without turning the surfaces grey.
- **The command palette no longer offers what would quietly do nothing.** Only the focus path is listed: leaving a tab cold-unmounts the panel you left, and nothing reloads it.

### Bug Fixes

- **pigit's status poll no longer takes the index lock.** `git status` is not read-only — it takes `.git/index.lock` to write back the stat cache it just refreshed — so a background poll landing on a checkout or a commit made that write fail with "Unable to create index.lock", which is how a merge flow ended in "Checkout back failed". Measured through pigit's own path, a poll against a checkout broke 231 of 240 checkouts; with `GIT_OPTIONAL_LOCKS=0`, none of 240. Nothing pigit does reads that cache back, and `setdefault` leaves a user who set the variable their own value.
- **A key pressed while a working-tree rewrite was running was reported as a failure.** A refusal is not an error: nothing was attempted. It goes to the header badge now, whose slot the spinner does not share — the old toast evicted the spinner, the one thing explaining why nothing had happened. Panel navigation is refused for the same reason: arriving at a panel mounts it, and Status reads the worktree the moment it appears.
- **The merge sequence stops hanging when the push never runs.** A busy network or an alert that never showed left it waiting on a callback that could not come, so it never checked out back and never cleared its state. It also leaves you on the page you were on instead of routing to Branch, and reloads the header as well as the panels — the push's own reload raced the checkout back.
- **The Branch page went blank when its scope matched nothing.** It set its message into the rows, but the row description returned no segments at all once the list was empty, so the page read as empty while quietly holding the text. Commit had a placeholder branch for exactly that case; every list page carries its message in the same place now.
- **A sheet stopped answering clicks after the terminal got shorter.** A sheet is anchored to the bottom edge and paints from the live surface height, but its click region was derived from the terminal height when it was last sized. Any height-only resize moved the sheet on screen and left the hit region behind, so a click was swallowed by whatever the stale region now covered. It reached every sheet, not only the commit editor.

## 2.10.0 (2026-10-08)

### Breaking Changes

- **The contribution graph left the Commit panel.** It was a strip under the commit list, toggled with `Ctrl+r`, and it only appeared on panels taller than 19 rows — so on a short terminal it did not exist at all. It is the **Graph** tab now (`5`), reachable at any height, and `Ctrl+r` went with the strip.
- **`app.commit_report_default` is retired.** The key turned that strip on and off; there is no strip. A config that still carries it now warns and is ignored rather than failing, the way `auto_refresh_interval` is, so nothing has to be edited by hand.

### Features

- **A Graph tab: the contribution heatmap, a per-author chart, and a punch card.** Commits by weekday and hour answer what the heatmap cannot — *what time of day* rather than *which day*. Each graph is a whole block now (its plot, its labels, its legend) reporting the size it needs, and the panel lays them out on a board that wraps them to the width it is given, so the arrangement follows the terminal instead of constants chosen for one size. A fixed wordmark takes the top rows: it does not wrap and does not pan with the graphs, and the panel's right edge clips whatever of it does not fit.
- **The graphs say what is off screen, and keep what you were reading in view.** A window onto a larger canvas looked like all there was, so each edge now carries a mark when the canvas continues that way. Narrowing the terminal re-flows the blocks — which wraps more, makes the canvas *smaller*, and used to drag the window back and lose the block you were on; the board now remembers the block the window was nearest to and scrolls it back into view.
- **The diff's file bar shows each file's `+N −M`.** It said which file of how many, not how big it was, so a commit touching twenty files opened onto a wall with no skeleton. The counts come from lines already in memory, so the bar costs no extra `git`.
- **An error toast is copied to the clipboard.** A toast lives three seconds and the clipboard does not — and a failure message is exactly what you would paste into an issue. Every toast is announced on a signal and the app copies the error ones; an empty message is skipped, because copying it would clear the clipboard.

### Improvements

- **The list panels share one row grammar.** Each had invented its own, so the column a row's identity started in depended on which panel you were looking at — and inside the Status panel, on which row: directory rows reserved one cell where file rows reserved four, putting their icons, and therefore their names, three columns apart. Prefixes are fixed-width lanes in a fixed order now, and an unused lane reserves its cells instead of collapsing. Two consequences are visible: the Commit panel's subject column no longer moves with the width of that row's refs — a commit carrying `(HEAD -> main, v0.4.0)` used to push its subject 24 columns right of the next row's — and the cursor is drawn with the same accent bar in every panel.
- **The Stash panel stops holding a quarter of the screen when it is empty.** Two lines of empty state under a header rule were being given a quarter of the screen, capped at ten rows, and every one of those rows came out of Status's own.
- **The diff gutter numbers only lines that are in a file.** It numbered whatever it could not classify, so a `git show` stream ran 0,1,2,… through the commit subject, then through `diff --git`, `index` and `new file mode`, and only then restarted at the hunk's own first line — three unrelated sequences sharing one column.

### Bug Fixes

- **An overlay drawn across wide characters threw its own row off by a column.** A wide glyph is stored as two cells, and every write replaced one half and left the other — which still renders a column, so the row came out one column wider or narrower than the terminal and everything after the split shifted with it. Opening Help over commit rows carrying CJK text put the popup's border a column off on each row it crossed, and whether it happened at all came down to the terminal width.
- **`exec` left its children an inherited stdin, and `git shortlog` reads the log from it.** A command that decides to read stdin waits for an EOF that never arrives while ours is an open pipe, and blocks its caller with nothing reported. `shortlog` with no revision is exactly such a command, which is how the test suite came to hang intermittently; it is now given `HEAD` explicitly, since feeding it an immediate EOF would trade a visible hang for a silently empty answer.
- **A merge commit's diff was read as a single file.** A combined diff opens each file with `diff --cc` and names one path, while every reader that decides where a file's block ends looked for `diff --git` — so the file bar listed no files at all, the second file's headers fell inside the first file's hunk, and not one content line of the merge was syntax-highlighted. The boundary is one predicate now, and it takes `diff --cc` and `diff --combined` the way it takes `diff --git`.

## 2.9.1 (2026-10-06)

### Breaking Changes

- **Skipping the danger confirmation is now something you ask for.** `pigit cmd` skipped it whenever the `CI` environment variable was set — a variable CI systems set by themselves — so a force push, a branch delete, a stash drop or a file restore ran unconfirmed there, including the double confirmation for destructive commands, with the user never choosing it. It now takes `--yes` (`-y`). Existing CI scripts that relied on the old behaviour need the flag; without it the command is refused rather than assumed, which is the safe direction.

### Improvements

- **commit and amend no longer block the UI**: they were the last two file actions still calling `git` on the UI thread, and `commit` is the one that runs a pre-commit hook — the case where the freeze is unbounded. Both now run on a worker behind a spinner. They also take the worktree gate, because they move HEAD and not just the index: a checkout running on a worker would otherwise move the tip the commit lands on. That gate incidentally closes a double-submit window the change opened — the editor sheet stays up while the worker runs, so a second `submit` is now refused with the busy message instead of racing the first.
- **Commit and Branch show a skeleton while loading**: only Status had one, so "empty" and "still loading" looked the same on the other two.
- **The footer shows `? Help`.** It listed only Inspect and Quit, so nothing pointed at `?` — the entry point to every binding that is not on screen.
- **The current branch is marked in text.** HEAD and an ordinary local branch rendered identical text, leaving colour as the only difference; the row now carries a `*`, the way `git branch` writes it.
- **Branch and Stash rows show their age.** Both lists were already sorted by date and neither displayed it — Branch asked git for `--sort=-committerdate` and then threw the date away. A missing date renders as nothing rather than a bogus age.

### Bug Fixes

- **The confirmation dialog could push its own buttons off screen.** `AlertDialog` took its height straight from the message, and a dialog taller than the terminal is drawn from row 0 and clipped at the bottom — taking the footer with it. A batch-undo confirm of a dozen records needed 31 rows on an 80x24 terminal, leaving neither OK nor Cancel visible and nothing to say Esc still worked. The body is now capped at what fits, the rest is reachable with the arrow and page keys, and the window position rides the frame title so the indicator costs no message rows.
- **Every user-facing string is English.** Seven were not: two identically worded toasts, two worktree guards, the reflog confirm, a fullwidth comma joining commands in the undo confirm, and one module header. The separator was the one that would have been missed — it is not a message but `describe_commands`'s join, which renders on the `Run:` line of every undo confirmation. A test now tokenizes every module and fails on a non-English string literal.
- **The repo registry is written atomically, and damage stays recoverable.** `dump_repos` truncated the destination and wrote in place, so a crash mid-write left a half-written file; `load_repos` folded "cannot parse" in with "not there" and returned empty for both. Together with `before_hook`, which rewrites the registry on every start, that turned damage into data loss: the next launch replaced the unreadable file with just the current repo. Writes now go beside the target and are moved into place, and a file that will not parse is set aside under a numbered `.corrupt` name first.
- **`repo clear` asks first.** It unlinked the registry with no prompt at all, which no other destructive path in the tool does.
- **A failed bulk run reaches the caller.** `repo fetch/pull/push` printed a summary and returned nothing, so the process exited 0 whether every repo succeeded or none did. A picker that could not run at all was worse: with no terminal and no explicit names it exited non-zero without a message, which was read as a cancellation — nothing printed, exit 0, in exactly the environment scripts run in.
- **An empty repository no longer reports a filter it never had.** The Commit panel printed "No matching commits." whenever the list was empty, including a fresh repository where no query had been typed.
- **Branch fields are split on NUL, not `|`.** A branch name may contain `|`, and such a name shifted every field after it — the name, the upstream and the ahead/behind counts all came out wrong, silently.

## 2.9.0 (2026-10-01)

### Features

- **Streaming commit history**: the list was capped at 300 commits and read in one shot, so every refresh materialised the whole log on a worker and then rebuilt every row on the UI thread — raising the cap alone could only jank. History now arrives in batches of 500 and is appended as it arrives, keeping the cursor, its sub-row and the scroll offset where they were; a cancelled read drops the generator and closes the `git` pipe. The cap becomes the `commit_log_limit` setting (20000, `0` for unlimited). Commit bodies are read for the rows around the cursor instead of prefetching 300 messages up front, cached per sha, so painting never runs `git`.

### Improvements

- **Working-tree operations no longer freeze the UI**: merge (`m`) and every Status panel file action — stage, stage all, discard, ignore, checkout ours/theirs — ran inline on the UI thread, costing one `git` subprocess per file. A stage-all after a large refactor froze the screen for the whole loop. They now run on a worker behind a spinner. The spinner had never painted in these paths either: `show_spinner` only sets the render flag, which the event loop services once the key callback returns — and it was the callback that was blocking.
- **Quitting no longer waits on background work**: the thread pool is not a daemon pool, so interpreter shutdown joined every worker. A `git pull` against an unreachable remote has no upper bound, which left the process alive after the terminal was restored, with nothing on screen saying why. Quitting with work in flight now asks first; answering yes drops the queued tasks and leaves without the join. An ordinary quit winds down exactly as before.

### Bug Fixes

- **Undo, failures and worktree rewrites**: `stash pop` recorded an empty undo payload, so `u` failed with `'stash_sha'` and silently consumed the record. Background worker failures were debug-logged and dropped, leaving a stale panel that read as "nothing more to show" — they now surface as a toast naming the action. A confirm-gated action whose dialog was refused (another modal open) did nothing at all, indistinguishable from a dead key. `can_merge`/`can_rebase` turned a failed probe into "go ahead" and would start a merge on a worktree they could not inspect. `create_branch` and `amend` were not reversible; both are now (amend reverses with a soft reset, so the pre-amend state comes back exactly).
- **Worktree gate coverage**: the single-flight gate only covered the panel view models. Merge, rebase, cherry-pick, the sequencer controls, undo, pull and `ignore` all rewrite the working tree too, so each now defers to it. Undo matters most: `rewind_head` guards on a clean worktree, and a half-written tree is exactly what makes that guard pass wrongly. Nine copies of the same refusal collapsed into one helper, and pull releases only a gate it actually took.
- **Wide characters**: horizontal scrolling clipped by character index while its offset was in columns, over-clipping any run starting with a wide glyph. A zero-width mark is now appended to the base cell the drawing loop is holding, never looked up in the row — reaching back risked editing a cell that is still the shared blank singleton, which would have drawn the mark on every blank cell for the life of the process. File-history subjects and the filter bar truncate by display width.
- **`NO_COLOR`**: honoured, after `PIGIT_COLOR_MODE` so an explicit request for colour still wins.
- **Diff viewer**: scrolling left hid the start of every line with nothing said about it, while the right edge has always drawn "…"; it now shows a matching marker. `slice_left_by_width` kept combining marks whose base it had just cut away, so a terminal drew the accent over the blank left by a half-cut wide glyph or over the previous word. The viewer also accepts arrow keys — it was the only list that did not — and global footer hints resolve from their bindings, so a remapped key shows up and `q` is no longer hidden.
- **Merge key help direction**: the binding merges the current branch into the selected one (the confirmation asks "Merge `<source>` into `<target>`?"), but the help text claimed the opposite. In-app description and both doc tables now match.

### Tests

- `TestRepo` built a fixed `tests/test_repo`, so two concurrent pytest runs re-initialised it under each other; it now uses `tmp_path_factory`. The commit panel gained the observe-driven-refresh regression test the other list panels already had.

## 2.8.0 (2026-09-17)

### Features

- **Commit author email**: the expanded (`z`) Author row and the Inspector commit snapshot now show the author's email beside the name (`Zev <zev@example.com>`). The email is carried through the commit log listing; authors without one still render name-only.

### Bug Fixes

- **Python multi-line strings**: an assigned or prefixed triple-quoted string (`ROW_SQL = """`, `f"""`, `r"""`) is recognised wherever it starts on the line, not only at the start of a line. Its body highlights as a string, and its own closing quotes no longer flip the rest of the file into docstring colour.
- **Word-level diff**: removals and additions are paired per change run instead of by index across the whole hunk (two runs in one hunk no longer compare across the context line between them), each run's two sides are diffed as one text stream so unequal counts still line words up with their counterparts, words are tokenised as whitespace-delimited runs like `git diff --word-diff` (a dotted name changes as a unit), and indentation is never marked.

## 2.7.0 (2026-09-09)

### Features

- **Sub-row navigation in expanded commit messages**: a `z`-expanded commit item that spans multiple rows now moves the cursor sub-row by sub-row, so long commit bodies can be read line by line instead of jumping straight to the next commit. Enter-actions still act on the commit under the cursor.

### Bug Fixes

- **Multi-line comment & conflict-marker highlighting in diffs**: the cross-line comment/docstring state is now resolved from the full old and new file content (git blob, or the worktree file for unstaged sides) instead of the truncated `-U3` fragment, so an edit in the middle of a block comment no longer gets colored as code, and real code after a `*/` that falls outside the hunk is no longer dimmed. The state scanner is also string-aware: a `/*` inside a string literal (e.g. a Go raw string) no longer dims the rest of a new file. Conflict markers (`<<<<<<<` / `=======` / `>>>>>>>`) render as markers in their own color instead of being tokenized as code, and no longer bleed comment state across sides.
- **Inspector and Welcome sheets scroll with the mouse wheel**.
- **Repo switcher shows live branch names**: the branch column reflects the repository's current branch and refreshes without blocking while the switcher is open.

### Performance

- **Render once per input batch**: the event loop redraws after a burst of queued input instead of once per event, removing ghost wheel scroll and redundant frame renders.

## 2.6.1 (2026-09-03)

### Features

- **Brand-accent diff border**: the full-screen diff viewer's border renders in the theme's brand accent while the diff is the active view, receding to the inactive tone when an overlay takes focus (fixes #81).
- **Onedir binary distribution**: a PyInstaller build (`pigit.spec` + `binary.yml`) ships macOS/Linux bundles attached to the GitHub Release on version tags. The bundle carries a single `pigit` executable; `g`/`r` become opt-in shell aliases (`alias g='pigit cmd'`, `alias r='pigit repo'`).

### Bug Fixes

- **Chinese filenames in tree mode**: git status now runs with `core.quotepath=false`, so non-ASCII paths arrive raw instead of octal-escaped strings that tree view then split into fake directories.

### Docs

- MkDocs site gains Archify runtime, sequencer, and palette diagrams.

### CI

- Docs deploy uses `actions/deploy-pages` v5, dropping the Node 20 deprecation warning.

## 2.6.0 (2026-08-31)

### Features

- **Reflog lightweight recovery**: `; reflog` in the command palette lists the last 50 HEAD reflog entries; picking one confirms then hard-resets to it (same dirty-worktree guard as undo), records a rewind point so the recovery itself is `u`-reversible, and the empty-undo toast now points at `; reflog`.

### Performance

- **Startup up to 54% faster**: `pigit -v` drops from ~210ms to ~97ms with zero git subprocesses spawned at import (termui modules loaded: 61 → 0). Repo bootstrap moves to the TUI/count/repo commands, `get_git_dir`/`get_git_common_dir` use git's absolute-path commands, observe initialization moves off the first frame (two-phase resolve/attach), and `asyncio` imports lazily in the async executor.

### Bug Fixes

- **AlertDialog wraps by display width**: full-width CJK characters no longer overflow the content box and paint over the dialog border (visible in the reflog confirm dialog).

### Refactors

- AlertDialog width is now terminal-derived (`max(40, term_cols*3//7)`) instead of scattered hardcoded 50/40 values.
- `add_repos(confirm=False)` skips re-confirming an already-validated path; `auto_append` now triggers only for TUI/count/repo commands.

### Docs

- New MkDocs user site with pigit-themed styling, published via GitHub Pages CI.

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
