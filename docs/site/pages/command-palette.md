# Command Palette

Press **`;`** anywhere in the TUI to open the command palette.

## How checkout runs

`;` → type `checkout` + space → pick a branch → **Enter**. The App then calls
`GitApi` / `git`.

[Open fullscreen](assets/archify/pigit-palette.sequence.html){ target=_blank .md-button }

<div class="archify-embed" markdown="0">
  <iframe
    class="archify-frame"
    src="../assets/archify/pigit-palette.sequence.html"
    title="Command palette checkout sequence"
    loading="lazy"
    referrerpolicy="no-referrer"></iframe>
</div>

## Static commands

Type to filter by command id or description. Press **Enter** to run the
highlighted item, or type a full command id when nothing matches.

| Command | Description |
|---------|-------------|
| `status` | Switch to Status panel |
| `branch` | Switch to Branch panel |
| `commit` | Switch to Commit panel |
| `stash` | Focus Stash panel |
| `push` / `pull` / `fetch` | Network sync |
| `quit` | Exit pigit |
| `continue-merge` | Continue merge (when merging) |
| `rebase-*` / `cherry-pick-*` | Sequencer controls (when active) |

Merge/rebase/cherry-pick entries appear only while that operation is in
progress.

## Parameterized commands

Type a command, then **space**, to switch to argument completion:

| Command | Completes | Runs |
|---------|-----------|------|
| `checkout` | Branch names | `git checkout` via Branch VM |
| `merge` | Branch names | Merge workflow (with guards) |
| `stage` | Working-tree paths | Stage file (skips already-staged) |
| `gitignore` | Working-tree paths | Add path to `.gitignore` |
| `reflog` | Reflog entries | Recover HEAD from reflog (confirm + dirty guard) |

Examples:

```
checkout dev
merge feature/login
stage src/app.py
reflog HEAD@{2}
```

### Tab completion

After filtering, use **↑/↓** to highlight a candidate and press **Tab** to
fill the full command (including the argument) into the input line. Press
**Enter** to execute.

### Reflog entries

Reflog candidates show `{sha7} {message} · {relative time}` but submit the
full SHA for reliable dispatch. Recovery asks for confirmation, refuses dirty
worktrees, runs `git reset --hard`, and records an undo point so **`u`** can
reverse the recovery itself.
