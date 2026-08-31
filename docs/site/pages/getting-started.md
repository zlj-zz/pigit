# Getting Started

## Requirements

- **Python 3.11+**
- An interactive terminal (stdin and stdout must be TTYs)
- **macOS / Linux** for the full TUI; on Windows, CLI sub-commands are available

## Installation

```bash
pip install -U pigit
```

From source:

```bash
git clone https://github.com/zlj-zz/pigit.git --depth=1
cd pigit
pip install -e .
```

Development install:

```bash
pip install -e ".[dev]"
```

## First run

```bash
pigit
```

The TUI opens automatically when you run `pigit` with no sub-command.

<figure markdown="span">
  ![pigit interaction demo](assets/demo_interaction.gif){ width="720" }
  <figcaption>Panel navigation, staging, and the command palette (recorded from the TUI).</figcaption>
</figure>

### Essential keys

| Key | Action |
|-----|--------|
| ++1++ / ++2++ / ++3++ / ++4++ | Status / Stash / Branch / Commit |
| ++tab++ | Cycle panels |
| ++semicolon++ | Command palette |
| ++question++ | Key bindings for the focused panel |
| ++u++ | Undo last action |
| ++q++ / ++esc++ | Quit / back |

!!! tip "Command palette"
    Press ++semicolon++, type a command name, then **space** to complete branch or
    file arguments. Use **Tab** to fill the selected candidate into the input line.

The full binding list lives in the [Keyboard Reference](keyboard-reference.md).

## Shell integration

Generate completion scripts and the `repo cd` wrapper:

```bash
eval "$(pigit --init)"
```

Add that line to `~/.bashrc`, `~/.zshrc`, or your fish config. Supports
`bash`, `zsh`, and `fish`.

## Next steps

| Topic | Page |
|-------|------|
| Panel workflows and diff viewer | [TUI Guide](tui-guide.md) |
| `; checkout`, `; reflog`, Tab completion | [Command Palette](command-palette.md) |
| Daily commit flow, undo vs reflog | [Workflows](workflows.md) |
| Non-interactive commands | [CLI](cli.md) |
| `pigit.toml`, key remapping | [Configuration](configuration.md) |
| TTY, icons, stale panels | [Troubleshooting](troubleshooting.md) |

## Build the docs locally

```bash
pip install mkdocs-material
mkdocs serve --config-file docs/site/mkdocs.yml
```

Open the URL printed in the terminal (usually `http://127.0.0.1:8000`).
