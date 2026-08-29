<div align="center">

<pre>
 ____ ___ ____ ___ _____
|  _ \_ _/ ___|_ _|_   _|
| |_) | | |  _ | |  | |
|  __/| | |_| || |  | |
|_|  |___\____|___| |_|
</pre>

## ⚡ A terminal UI for Git — short commands · multi-repo management

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/pigit?label=PyPI&color=orange&logo=pypi&logoColor=white)](https://pypi.org/project/pigit)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Coverage](https://codecov.io/gh/zlj-zz/pigit/branch/main/graph/badge.svg)](https://codecov.io/gh/zlj-zz/pigit)
[![macOS](https://img.shields.io/badge/macOS-✓-000000?logo=apple&logoColor=white)]()
[![Linux](https://img.shields.io/badge/Linux-✓-9cf?logo=linux&logoColor=white)]()

`pigit` — a Git assistant for the terminal: **TUI panels** 🖥️ · **short commands** ⌨️ · **multi-repo management** 📚

</div>

<div align="center">
  <img src="./docs/resources/demo_interaction.gif" width="80%" alt="interaction demo">
</div>

## 🚀 Quick Start

```bash
$ pip install -U pigit

$ pigit                 # launch the TUI
$ pigit cmd -l          # list short commands
$ pigit repo add ~/dev/foo ~/dev/bar
$ pigit repo ll         # summary across repos
$ pigit open            # open remote in browser
```

> 💡 **The TUI opens on the first `pigit` run** — `1/2/3/4` switch panels, `;` opens the command palette (type a command, then space to complete branch/file arguments), `?` shows every key binding.

---

## 📦 Installation

### From source

```bash
git clone https://github.com/zlj-zz/pigit.git --depth=1
cd pigit
make install
# or on Windows
python setup.py install
```

### Development (editable install)

```bash
pip install -e ".[dev]"
```

---

## 🖥️ TUI Mode

Pigit's primary interface is a terminal UI. Simply run `pigit` to enter it — four core panels plus a global command palette:

| panel | what you can do |
|-------|------------------|
| **Status** 📂 | stage / unstage / discard / ignore files; inline diff; copy path (`Y`); stash list; file preview on wide terminals |
| **Diff** 🎭 | stage individual hunks; browse file history (`v`, `p`/`n`); word-diff + syntax highlighting |
| **Commit** 🗂️ | inline subject/body editor with lint feedback |
| **History** ↩️ | undo the last action, browse and reverse multiple steps |
| **Branch** 🌿 | checkout, create, rename, delete branches; scope to a sub-directory (`R`) |

### Key bindings

| key | action | panel |
|-----|--------|-------|
| `j` / `k`, `↑` / `↓` | navigate lists | all |
| `Enter` | select / open | all |
| `q` / `Esc` | back / quit | all |
| `?` | help | all |
| `;` | open command palette (type a command; space + fragment completes branch/file args, `Tab` fills) | all |
| `I` | inspect selection (top sheet; `j`/`k` scroll, `Esc`/`I` close) | Status, Stash, Branch, Commit |
| `a` / `d` / `i` | stage / discard / ignore | Status |
| `c` | inline commit editor | Status |
| `c` | cherry-pick onto HEAD | Commit |
| `o` | show another branch’s log | Commit |
| `Enter` | show that branch’s commits (no checkout) | Branch |
| `H` | toggle hunk staging | Diff |
| `u` / `U` | undo last action (confirm) / undo stack — also reverses merge, rebase, cherry-pick | all |
| `z` / `Z` | stash push / pop | Status |

Press `?` for the full per-panel list. Every key is remappable via `[app.keybindings]` — see [Keybindings](#keybindings).

For operations that are cumbersome on the command line—such as staging individual hunks, browsing commit history with inline graphs, or resolving merge conflicts—the TUI is the recommended workflow.

> [!NOTE]
> The TUI runs on macOS / Linux and requires an interactive terminal (both stdin and stdout must be TTYs). It will not launch in CI pipelines, scripts, or when piped. On Windows, only the CLI sub-commands are available.

---

## ⌨️ CLI Usage

For scripting, CI, or quick tasks, Pigit exposes sub-commands and flags.

```bash
usage: pigit [-h] [-i] [-f] [-r] [-v] [-c [PATH]] [--create-ignore TYPE]
             [--init [SHELL]] [--create-config] [--with-keybindings]
             {cmd,repo,open} ...

Pigit TUI is called automatically if no parameters are followed.
```

### `cmd` — short commands

Short aliases for common git operations.

<div align="center">
  <img src="./docs/resources/demo.gif" width="80%" alt="demo display">
</div>

**Discovery**

- `pigit cmd -l` — list all short commands with help text and underlying `git` lines.
- `pigit cmd -s <query>` / `--search <query>` — filter by keyword.
- `pigit cmd -t <category>` — filter by category (branch, commit, index, etc.).
- `pigit cmd -p` / `--pick` — interactive picker (TTY only): `j`/`k` to move, `Enter` to run, `/` to filter, `q` to quit.

Example output from `pigit cmd -l`:

```
These are short commands that can replace git operations:
    b        lists, creates, renames, and deletes branches.
             git branch
    bc       creates a new branch.
             git checkout -b
    bl       lists branches and their commits.
             git branch -vv
    bd       delete a local branch by name.
             git branch -d
......
```

### `repo` — multi-repo management

Manage multiple repositories at once.

- `pigit repo add <path>` — add repo(s) to the managed list.
- `pigit repo rm <name>` — remove repo(s).
- `pigit repo ll` — display summary of all repos.
- `pigit repo cd <name>` — print the path of a managed repo.
- `pigit repo cd -p` — open the interactive picker to choose a repo.
- `pigit repo cd --output-file <path>` — write the selected path to a file instead (for scripts/CI).
- `pigit repo fetch|pull|push [<name>...]` — run git operations across repos in parallel.

### `open` — open remote in browser

Open the current repository's remote URL in a web browser.

```bash
pigit open              # open current branch
pigit open <branch>     # open specific branch
pigit open -c           # open at current commit
pigit open -i <number>  # open a specific issue
pigit open -p           # print URL instead of opening
```

### Other flags

| flag | description |
|------|-------------|
| `-i`, `--information` | show repository info |
| `-f`, `--config` | display local git config |
| `-r`, `--report` | show pigit description |
| `-c [PATH]`, `--count [PATH]` | code statistics (table or simple format) |
| `--create-ignore TYPE` | generate a `.gitignore` template |
| `--create-config` | create a config file at `~/.config/pigit/pigit.toml` |
| `--with-keybindings` | with `--create-config`, dump commented keybinding defaults into the config |

---

## 🔌 Shell Integration

`pigit --init` generates shell completion scripts **and** a `pigit` wrapper function.

> [!TIP]
> Run `--init` once: it sets up both tab-completion and the `repo cd` auto-`cd` wrapper. You do not need a separate completion-only step.

Add it to your shell configuration:

```sh
# ~/.bashrc or ~/.zshrc
eval "$(pigit --init)"
```

Supports `bash`, `zsh`, and `fish`. If no shell is specified, it auto-detects from `$SHELL`.

### Auto `cd` with `repo cd`

After sourcing the init script, `pigit repo cd -p` automatically changes your shell's working directory when you pick a repo. The wrapper intercepts `pigit repo cd`, runs the picker, and `cd`s into the selected path.

For scripts and CI, use `--output-file <path>` to write the selected directory to a file instead.

---

## 🛠️ Configuration

Create a template config with `pigit --create-config`. The config lives at:

- Linux/macOS: `~/.config/pigit/pigit.toml`
- Windows: `%USERPROFILE%\pigit\pigit.toml`

See [`examples/pigit.toml`](./examples/pigit.toml) for a full template.

| section | key | type | default | description |
|---------|-----|------|---------|-------------|
| `[cmd]` | `display` | bool | `True` | show original git command |
| `[cmd]` | `recommend` | bool | `True` | suggest corrections for wrong commands |
| `[counter]` | `use_gitignore` | bool | `True` | respect `.gitignore` when counting |
| `[counter]` | `show_invalid` | bool | `False` | show files that cannot be counted |
| `[counter]` | `show_icon` | bool | `True` | show file icons (requires Nerd Font) |
| `[counter]` | `format` | str | `table` | output format: `table` or `simple` |
| `[info]` | `git_config_format` | str | `table` | git config display: `table` or `normal` |
| `[info]` | `repo_include` | list | `["remote", "branch", "log"]` | sections to show in repo info |
| `[repo]` | `auto_append` | bool | `True` | auto-add current repo to managed list |
| `[log]` | `debug` | bool | `False` | debug mode |
| `[log]` | `output` | bool | `False` | print logs to terminal |
| `[app]` | `repo_observe` | bool | `True` | observe git metadata and refresh panels when the repo changes |
| `[app]` | `observe_worktree` | bool | `True` | also observe worktree files for Status list updates |
| `[app]` | `word_diff` | bool | `True` | enable word-diff in the diff viewer |
| `[app]` | `status_view` | str | `tree` | status panel default view: `flat` or `tree` |
| `[app]` | `diff_preview_default` | bool | `True` | show Status/Stash side diff preview on large screens (Ctrl+p on Status/Stash) |
| `[app]` | `log_graph_default` | bool | `True` | show Branch log-graph preview on large screens (Ctrl+p on Branch) |
| `[app]` | `commit_report_default` | bool | `True` | show the Commit contribution-graph report below the list when the panel is taller than 19 rows (Ctrl+r toggles) |
| `[app]` | `show_footer` | bool | `True` | show the footer key-hint bar |
| `[app]` | `icons` | str | `auto` | Nerd Font icon policy in the Status list: `auto` (detect kitty/WezTerm/Alacritty/Ghostty), `on`, `off` (fall back to plain symbols; `PIGIT_ICONS=0` forces off) |

### Keybindings

Remap app actions with an `[app.keybindings]` section. Keys are semantic strings
(`"c"`, `"down"`, `"ctrl c"`, `" "` for space); use an array for multiple keys.

To list every configurable action with its default key, regenerate the config with:

```bash
pigit --create-config --with-keybindings
```

This appends a commented `[app.keybindings]` block to the generated file (existing
overrides are preserved as active lines). For example:

```toml
[app.keybindings.branch]
checkout = "C"  # default: "c"
# next = ["j", "down"]  # Navigate branch list
```

Actions are scoped by namespace: `universal`, `status`, `diff`, `rebase`,
`branch`, `commit`, `stash`, `recent`.

---

## 🧩 Custom Commands

Define aliases and scripts in `pigit.cmds.toml` inside the pigit home directory.

### Aliases

```toml
[cmd_new.aliases]
mybl = "bl"
mylog = "log --oneline --graph"
```

### Scripts

```toml
[cmd_new.scripts.myscript]
steps = ["status", "log --oneline"]
help = "Show status then log"
category = "script"

# concise form for simple step lists
[cmd_new.scripts]
quick-check = ["status", "diff --cached"]
```

User-defined entries appear in `pigit cmd -l`, search, and `--pick` with `[alias]` or `[script]` prefixes.

---

## ✨ Features

**🖥️ TUI**

- **Session history / undo** ↩️ — one-key reversal with confirmation (`u`), a browsable undo stack (`U`), and undo for merge, rebase, and cherry-pick.
- **Command palette** 🎯 — `;` opens a filterable command list; parameterized commands (checkout/merge/stage/gitignore) complete branch/file arguments.
- **Hunk staging** 🔪 — stage or unstage individual hunks directly in the diff viewer (`H`).
- **Inline commit editor** ✍️ — subject/body fields with lint bar inside the TUI.
- **Stash management** 🗄️ — push, pop, and drop stashes from the status panel.
- **Auto refresh** 🔄 — periodic background refresh of the active panel while the TUI is idle.
- **Syntax highlighting** 🎨 — diff and file-history views tokenize source code by language (word-diff included).
- **Adaptive layout** 📐 — side-by-side preview panel on large terminals.
- **Inspector sheet** 🔍 — `I` opens a frozen selection snapshot as a top overlay (not a layout column).

**⌨️ CLI**

- **Short commands** ⚡ — aliases like `pigit cmd st` for `git status --short`.
- **Command correction** 🔧 — suggests the right command when you typo.
- **Code statistics** 📊 — count lines/files by type with table or simple output.
- **`.gitignore` templates** 🧹 — generate from common types.
- **Quick open remote** 🌐 — open repo/commit/issue in browser.

**📚 Multi-repo & shell**

- **Multi-repo management** 🗂️ — `repo` sub-commands for bulk operations across projects.
- **Shell completion** 🐚 — bash/zsh/fish with `pigit --init`.
- **Auto `cd`** 📁 — shell wrapper enables `pigit repo cd -p` to change directory after picking.

**🎛️ Customization**

- **Custom keybindings** 🎹 — remap any app action via `[app.keybindings]`; dump defaults with `--create-config --with-keybindings`.

---

<div align="center">

**pigit** — terminal Git, all in one · ⭐ Star the repo if you find it useful!

</div>
