# Configuration

Create a template config:

```bash
pigit --create-config
pigit --create-config --with-keybindings
```

Config locations:

- Linux/macOS: `~/.config/pigit/pigit.toml`
- Windows: `%USERPROFILE%\pigit\pigit.toml`

See [`examples/pigit.toml`](https://github.com/zlj-zz/pigit/blob/main/examples/pigit.toml)
for a full template.

## Application

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `repo_observe` | bool | `true` | Refresh panels when git metadata changes |
| `observe_worktree` | bool | `true` | Also watch worktree files for Status updates |
| `word_diff` | bool | `true` | Word-diff in the diff viewer |
| `status_view` | str | `tree` | Status layout: `flat` or `tree` |
| `diff_preview_default` | bool | `true` | Side diff preview on large screens |
| `log_graph_default` | bool | `true` | Branch log-graph preview on large screens |
| `commit_report_default` | bool | `true` | Contribution graph below commit list |
| `show_footer` | bool | `true` | Footer key-hint bar |
| `icons` | str | `auto` | Nerd Font icons: `auto`, `on`, `off` |

## Command display

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `[cmd]` | `display` | `true` | Show underlying git command |
| `[cmd]` | `recommend` | `true` | Suggest corrections for typos |
| `[repo]` | `auto_append` | `true` | Auto-add cwd to managed repos |
| `[log]` | `debug` | `false` | Debug logging |
| `[log]` | `output` | `false` | Print logs to terminal |

## Keybindings

Remap actions under `[app.keybindings]`. Keys are semantic strings (`"c"`,
`"down"`, `"ctrl c"`, `" "` for space). Use arrays for multiple bindings.

Namespaces: `universal`, `status`, `diff`, `rebase`, `branch`, `commit`,
`stash`, `recent`.

Example:

```toml
[app.keybindings.branch]
checkout = "C"  # default: "c"
```

Regenerate commented defaults with `pigit --create-config --with-keybindings`.

## Custom commands

Define aliases and scripts in `pigit.cmds.toml` inside the pigit home directory.

**Aliases**

```toml
[cmd_new.aliases]
mybl = "bl"
mylog = "log --oneline --graph"
```

**Scripts**

```toml
[cmd_new.scripts.myscript]
steps = ["status", "log --oneline"]
help = "Show status then log"
category = "script"

[cmd_new.scripts]
quick-check = ["status", "diff --cached"]
```

User entries appear in `pigit cmd -l`, search, and `--pick` with `[alias]` or
`[script]` prefixes.
