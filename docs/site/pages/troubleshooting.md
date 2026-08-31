# Troubleshooting

## TUI does not start

Pigit requires an **interactive terminal** (stdin and stdout must be TTYs).

| Symptom | Cause | Fix |
|---------|-------|-----|
| Exits immediately in CI | Non-TTY stdout | Use CLI sub-commands (`pigit cmd`, `pigit repo`) |
| `pip install` then script fails | Python subprocess without TTY | Run `pigit` from a real shell |
| SSH session oddities | Broken `$TERM` | Export `TERM=xterm-256color` (or your emulator's value) |

!!! note "Windows"
    Full TUI support targets **macOS and Linux**. On Windows, use CLI
    sub-commands; WSL is the supported path for the TUI.

## Terminal too small

Minimum size is **65×10** columns×rows. Below that, pigit refuses to paint the
layout and shows a size warning.

Widen the window or zoom out in your terminal emulator before launching.

## Icons misaligned or missing

Config key `icons` controls Nerd Font glyphs beside file names:

| Value | Behavior |
|-------|----------|
| `auto` | Glyphs on kitty, WezTerm, Alacritty, Ghostty; plain 1-cell symbols elsewhere |
| `on` | Always use Nerd Font codepoints |
| `off` | Plain symbols only |

Set in `~/.config/pigit/pigit.toml`:

```toml
[app]
icons = "auto"
```

Or disable for a session: `PIGIT_ICONS=0 pigit`.

If icons are enabled but the font lacks glyphs, install a **Nerd Font** in your
terminal profile.

## Panels feel stale

Since 2.0, polling was replaced by **repo observation**:

```toml
[app]
repo_observe = true      # watch .git metadata (default)
observe_worktree = true # also watch working tree for Status
```

If you disabled these, re-enable them instead of looking for
`auto_refresh_interval` (removed in 2.0).

## Undo says nothing to reverse

Session undo (`++u++`) only covers actions recorded in the current session.
Use **`; reflog`** for recovery outside that stack — see
[Workflows → Recover](workflows.md#recover-from-a-mistake).

## Push / pull prompts or hangs

Global ++p++ / ++f++ and palette `push` / `pull` run with
`GIT_TERMINAL_PROMPT=0` (non-interactive). Credential helpers must be
configured in git; pigit will not open an interactive password prompt inside
the TUI.

## Still stuck?

- Run with debug logging: `[log] debug = true` in `pigit.toml`
- Open an issue with terminal emulator, OS, `pigit --version`, and steps to
  reproduce: [GitHub Issues](https://github.com/zlj-zz/pigit/issues)
