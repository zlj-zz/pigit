# Keyboard Reference

Press ++question++ in any panel for bindings scoped to that panel plus global
keys. Everything below is remappable — see
[Configuration → Keybindings](configuration.md#keybindings).

## Global

| Key | Action |
|-----|--------|
| ++1++ / ++2++ / ++3++ / ++4++ | Status / Stash / Branch / Commit |
| ++tab++ / ++shift+tab++ | Cycle panels |
| ++semicolon++ | Command palette |
| ++question++ | Help (click row, double-click to run binding) |
| ++u++ | Undo last session action (confirm) |
| ++shift+u++ | Browse undo stack |
| ++p++ / ++f++ | Push / Pull current branch |
| ++i++ | Inspector for current selection |
| ++b++ | Bisect sheet |
| ++ctrl+p++ | Toggle side preview (Status/Stash diff or Branch log graph) |
| ++q++ / ++esc++ | Quit / back |
| `@` | Repo switcher (managed repos) |

Header clicks: repo name opens the switcher; tab slots open an anchored panel
picker.

## Status

| Key | Action |
|-----|--------|
| ++j++ / ++k++ | Move selection |
| ++enter++ | Open diff (or expand/collapse directory in tree view) |
| ++a++ | Stage file or visual selection |
| ++shift+a++ | Stage all listed files |
| ++d++ | Discard changes |
| ++i++ | Add to `.gitignore` |
| ++c++ | Inline commit editor (staged files required) |
| ++shift+c++ | External `$EDITOR` commit |
| ++m++ | Amend HEAD with staged changes |
| ++s++ | Stash (optional message prompt, includes untracked) |
| ++v++ / ++shift+v++ | Visual multi-select / visual scroll |
| ++space++ | Toggle row selection (visual mode) |
| ++slash++ | Filter file list |
| ++ctrl+t++ | Tree / flat layout |
| ++h++ / ++l++ | Collapse / expand directory (tree) |
| ++j++ / ++k++ (preview) | Scroll side preview (++shift+j++ / ++shift+k++ when not in visual mode) |
| ++y++ | Copy file path |

## Stash

| Key | Action |
|-----|--------|
| ++enter++ | Open stash diff |
| ++a++ | Apply (keep in list) |
| ++p++ | Pop |
| ++d++ | Drop (confirm) |

Push stash from **Status** with ++s++ (optional message prompt).

## Branch

| Key | Action |
|-----|--------|
| ++enter++ | Show commits without checkout |
| ++c++ | Checkout |
| ++n++ | New branch |
| ++m++ | Merge into current |
| ++r++ | Interactive rebase onto selected branch |
| ++shift+r++ | Rename |
| ++d++ | Delete |
| ++p++ | Open create-PR URL in browser |
| ++ctrl+f++ | Cycle scope: local → remote → all |
| ++shift+j++ / ++shift+k++ | Scroll log-graph preview |

## Commit

| Key | Action |
|-----|--------|
| ++enter++ | View commit diff |
| ++c++ | Cherry-pick onto HEAD |
| ++o++ | Browse another ref's log |
| ++z++ | Toggle expanded commit rows |
| ++ctrl+r++ | Toggle contribution graph strip |
| ++slash++ | Filter by message or SHA |
| ++y++ | Copy commit SHA |

## Diff viewer

| Key | Action |
|-----|--------|
| ++j++ / ++k++ | Line up / down |
| ++shift+j++ / ++shift+k++ | Page up / down |
| `[` / `]` | Previous / next hunk |
| ++h++ | Toggle hunk mode |
| ++s++ / ++d++ | Stage / discard hunk (hunk mode) |
| ++comma++ / ++period++ | Previous / next file in commit |
| ++v++ | File history (commit diffs) |
| ++p++ / ++n++ | Older / newer commit (file history) |
| ++esc++ | Close diff |

## Command palette

| Input | Action |
|-------|--------|
| ++semicolon++ | Open palette |
| ++space++ after command | Switch to argument completion |
| ++tab++ | Fill highlighted candidate |
| ++enter++ | Run |

Parameterized: `checkout`, `merge`, `stage`, `gitignore`, `reflog`.

## Rebase sheet

Opened from Branch ++r++ before the sequencer runs.

| Key | Action |
|-----|--------|
| ++j++ / ++k++ | Move in todo list |
| ++shift+j++ / ++shift+k++ | Move commit down / up |
| ++p++ / ++s++ / ++f++ / ++r++ / ++e++ / ++d++ | pick / squash / fixup / reword / edit / drop |
| ++enter++ | Confirm and start rebase |
| ++esc++ | Cancel |

While a sequencer is active, palette entries such as `continue-merge`,
`rebase-continue`, and `cherry-pick-abort` appear under ++semicolon++.

## Bisect sheet (++b++)

| Key | Action |
|-----|--------|
| ++s++ | Start (`good [bad]`, bad defaults to HEAD) |
| ++g++ / ++b++ | Mark current commit good / bad |
| ++r++ | Reset bisect |
| ++esc++ / `@` | Close |

## Worktree picker

From repo switcher, press ++w++.

| Key | Action |
|-----|--------|
| ++plus++ | Add linked worktree |
| ++minus++ | Remove (dirty requires `--force` confirm) |
