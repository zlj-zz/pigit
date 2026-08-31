# TUI Guide

Pigit's primary interface is a terminal UI. Four core panels plus stash,
diff detail, and global overlays cover everyday Git work.

<figure markdown="span">
  ![pigit TUI demo](assets/demo.gif){ width="720" }
  <figcaption>Status, diff, commit editor, and branch operations.</figcaption>
</figure>

!!! tip "Quick lookup"
    Press ++question++ in any panel, or open the
    [Keyboard Reference](keyboard-reference.md) for a printable table.

## Panels

| Panel | Keys | What you can do |
|-------|------|-----------------|
| **Status** | ++1++ | Stage / unstage / discard / ignore; inline commit; visual multi-select; tree view; side diff preview |
| **Stash** | ++2++ | Apply, pop, drop; diff preview |
| **Branch** | ++3++ | Checkout, create, merge, rebase, rename, delete; log graph preview; open PR page |
| **Commit** | ++4++ | Browse log; cherry-pick; another ref's history; contribution graph |

## Navigation

| Key | Action |
|-----|--------|
| ++j++ / ++k++, ++up++ / ++down++ | Move selection |
| ++enter++ | Select / open |
| ++tab++ / ++shift+tab++ | Cycle panels |
| ++i++ | Inspector sheet for the current selection |
| ++ctrl+p++ | Toggle side preview (Status/Stash diff or Branch log graph) |

Click a **header tab slot** to open an anchored panel picker. Click the **repo
name** to switch managed repositories.

## Status panel

| Key | Action |
|-----|--------|
| ++a++ | Stage file or visual selection |
| ++shift+a++ | Stage all listed files |
| ++d++ | Discard |
| ++i++ | Ignore (add to `.gitignore`) |
| ++c++ | Inline commit editor (requires staged files) |
| ++shift+c++ | Commit via external `$EDITOR` |
| ++m++ | Amend HEAD with staged changes |
| ++s++ | Stash with optional message (includes untracked) |
| ++v++ / ++shift+v++ | Visual multi-select / visual scroll |
| ++space++ | Toggle row (visual mode) |
| ++slash++ | Filter files |
| ++ctrl+t++ | Tree / flat layout |
| ++y++ | Copy file path |

### Commit editor

Opened with ++c++ when files are staged:

1. Edit **subject** on the first line; body below the blank line.
2. The lint bar flags common issues (empty subject, overlong line).
3. Submit with ++enter++ or cancel with ++esc++.

## Diff viewer

Open from Status (++enter++) or full-screen on wide layouts.

| Key | Action |
|-----|--------|
| ++h++ | Toggle hunk mode |
| ++s++ / ++d++ | Stage / discard hunk (hunk mode) |
| `[` / `]` | Previous / next hunk |
| ++comma++ / ++period++ | Previous / next file in commit |
| ++v++ | File history (commit diffs) |
| ++p++ / ++n++ | Older / newer commit (file history) |
| ++esc++ | Close |

Word-diff and syntax highlighting follow `[app] word_diff` in config.

## Stash panel

| Key | Action |
|-----|--------|
| ++enter++ | View stash diff |
| ++a++ | Apply (keep in list) |
| ++p++ | Pop |
| ++d++ | Drop (confirm) |

Push stash from Status with ++s++ (message prompt).

## Commit panel

| Key | Action |
|-----|--------|
| ++c++ | Cherry-pick onto HEAD |
| ++o++ | Show another branch's log |
| ++z++ | Toggle expanded commit rows |
| ++ctrl+r++ | Toggle contribution graph (tall layouts) |
| ++slash++ | Filter by message or SHA |
| ++y++ | Copy SHA |

## Branch panel

| Key | Action |
|-----|--------|
| ++enter++ | Show commits (no checkout) |
| ++c++ | Checkout |
| ++n++ | New branch |
| ++m++ | Merge into current |
| ++r++ | Interactive rebase onto selected branch |
| ++shift+r++ | Rename |
| ++d++ | Delete |
| ++p++ | Open create-PR URL |
| ++ctrl+f++ | Cycle local / remote / all |

### Rebase sheet

Branch ++r++ opens the todo editor before git runs:

- ++shift+j++ / ++shift+k++ reorder commits
- ++p++ / ++s++ / ++f++ / ++r++ / ++e++ / ++d++ set pick / squash / fixup / reword / edit / drop
- ++enter++ confirm

## Undo and recovery

| Key | Action |
|-----|--------|
| ++u++ | Reverse the most recent session action (with confirmation) |
| ++shift+u++ | Browse the undo stack |

Undo covers staging, checkouts, merges, rebases, cherry-picks, and other
recorded HEAD moves. When nothing is available, the toast suggests
`; reflog` — see [Workflows](workflows.md#recover-from-a-mistake).

## Multi-repo, worktree, bisect

| Feature | How to open |
|---------|-------------|
| **Repo switcher** | Click header repo name or `@` |
| **Worktrees** | Switcher → ++w++ → ++plus++ / ++minus++ to add/remove |
| **Bisect** | ++b++ → ++s++ start, ++g++ / ++b++ mark, ++r++ reset |

Bisect and sequencers (merge/rebase/cherry-pick) are mutually exclusive.

## Help and welcome

- **First run**: Welcome sheet with panel map and core keys.
- **Any time**: ++question++ opens the Help browser — click a row to select,
  **double-click** to run that binding.

!!! note "TTY required"
    The TUI does not launch in CI pipelines, scripts, or when stdout is piped.
    See [Troubleshooting](troubleshooting.md).
