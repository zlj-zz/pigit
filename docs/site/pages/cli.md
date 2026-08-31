# CLI

For scripting, CI, or quick tasks, pigit exposes sub-commands and flags. The
TUI starts automatically when no sub-command is given.

```bash
pigit [-h] [-i] [-f] [-r] [-v] [-c [PATH]] [--create-ignore TYPE]
      [--init [SHELL]] [--create-config] [--with-keybindings]
      {cmd,repo,open} ...
```

## `cmd` — short commands

Short aliases for common git operations.

**Discovery**

```bash
pigit cmd -l              # list all short commands
pigit cmd -s <query>      # search by keyword
pigit cmd -t <category>   # filter by category
pigit cmd -p              # interactive picker (TTY only)
```

Example:

```
pigit cmd st              # git status --short
pigit cmd bc my-branch    # git checkout -b my-branch
```

Define custom aliases and scripts in `pigit.cmds.toml` — see
[Configuration](configuration.md#custom-commands).

## `repo` — multi-repo management

```bash
pigit repo add <path>           # add repo(s) to managed list
pigit repo rm <name>            # remove repo(s)
pigit repo ll                   # summary of all repos
pigit repo cd <name>            # print path of a managed repo
pigit repo cd -p                # interactive picker (TTY)
pigit repo cd --output-file F   # write selected path to file (scripts)
pigit repo fetch|pull|push      # parallel git across repos
```

With shell init (`eval "$(pigit --init)"`), `pigit repo cd -p` can auto-`cd`
into the picked repository.

## `open` — remote in browser

```bash
pigit open              # current branch
pigit open <branch>     # specific branch
pigit open -c           # at current commit
pigit open -i <number>  # issue page
pigit open -p           # print URL only
```

## Utility flags

| Flag | Description |
|------|-------------|
| `-i`, `--information` | Repository info |
| `-f`, `--config` | Local git config |
| `-r`, `--report` | Pigit description |
| `-c [PATH]`, `--count [PATH]` | Code statistics |
| `--create-ignore TYPE` | Generate `.gitignore` template |
| `--create-config` | Write `~/.config/pigit/pigit.toml` |
| `--with-keybindings` | Include commented keybinding defaults |
| `--init [SHELL]` | Shell completion + repo cd wrapper |
