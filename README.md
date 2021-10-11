# PIGIT

![Python 3](https://img.shields.io/badge/Python-v3.6%5E-green?logo=python)
[![pypi_version](https://img.shields.io/pypi/v/pigit?label=pypi)](https://pypi.org/project/pigit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A terminal tool for git. When we use git, do you feel very uncomfortable with too long commands. For example: `git status --short`, this project can help you improve it. This project is written in Python. Now most UNIX like systems come with Python. So you can easily install and use it.

![demo display](./demo.gif)

## Installation

### Pip

```bash
pip install -U pigit
```

### Source

```bash
git clone https://github.com/zlj-zz/pigit.git --depth=1
cd pigit
make install
# or
python setup.py install  # On windows
```

## Usage

You can run `pigit` in terminal, and you will see this intro:

```
[pigit] version: 1.3.2.dev
git version 2.30.1 (Apple Git-130)

Local path: /opt/homebrew/lib/python3.9/site-packages/pigit-1.3.2.dev0-py3.9.egg/pigit/__init__.py

Description:
  Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.
  It use short command to replace the original command, like:
  ``pigit ws`` -> ``git status --short``, ``pigit b`` -> ``git branch``.
  Also you use ``pigit -s`` to get the all short command, have fun and good lucky.
  The open source path on github: https://github.com/zlj-zz/pigit.git

You can use -h or --help to get help and more usage.

```

You can run `pigit -h` or `pigit --help` to get the help message. Like this:

```bash
usage: pigit [-h] [-v] [-C] [-s] [-p TYPE] [-t] [-d] [--out-log] [-f] [-i] [-c [PATH]]
             [--create-ignore TYPE] [--create-config] [--shell]
             [command] [args ...]

If you want to use some original git commands, please use -- to indicate.

positional arguments:
  command               Short git command or other.
  args                  Command parameter list.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         Show version and exit.
  -C, --complete        Add shell prompt script and exit.(Supported `bash`, `zsh`, `fish`)
  -s, --show-commands   List all available short command and wealth and exit.
  -p TYPE, --show-part-command TYPE
                        According to given type [Branch, Commit, Conflict, Fetch, Index,
                        Log, Merge, Push, Remote, Stash, Tag, WorkingTree, Submodule,
                        Setting, Extra] list available short command and wealth and exit.
  -t, --types           List all command types and exit.
  -d, --debug           Current runtime in debug mode.
  --out-log             Print log to console.
  --create-config       Create a preconfigured file of PIGIT.(If a profile exists, the
                        values available in it are used)

tools arguments:
  Auxiliary type commands.

  -f, --config          Display the config of current git repository and exit.
  -i, --information     Show some information about the current git repository.
  -c [PATH], --count [PATH]
                        Count the number of codes and output them in tabular form.A given
                        path can be accepted, and the default is the current directory.
  --create-ignore TYPE  Create a demo `.gitignore` file. Need one argument, support:
                        [android, c++, cpp, c, dart, elisp, gitbook, go, java, kotlin,
                        lua, maven, node, python, qt, r, ros, ruby, rust, sass, swift,
                        unity]
  --shell               Go to the pigit shell mode.

```

**For example**

You can use `pigit -s` to check what short command it suppored, it will display the corresponding help information and the original command, like this:

```
These are short commands that can replace git operations:
    b        lists, creates, renames, and deletes branches.
             git branch
    bc       creates a new branch.
             git checkout -b
    bl       lists branches and their commits.
             git branch -vv
    bL       lists local and remote branches and their commits.
             git branch --all -vv
    bs       lists branches and their commits with ancestry graphs.
             git show-branch
    bS       lists local and remote branches and their commits with ancestry graphs.
             git show-branch --all
    bm       renames a branch.
             git branch --move
    bM       renames a branch even if the new branch name already exists.
             git branch --move --force
    bd       delete a local branch by name.
             git branch -d
    c        records changes to the repository.
             git commit --verbose
......
```

### Interaction

It support a simple interactive mode. You can use `pigit ui` into the interactive mode and it let control the working tree simpler. like this:

![interaction demo](./interaction.gif)

And in the interaction mode, you can use `?` or `h` to see the help message.

### Open remote

You can use `pigit open` to open your remote website (just support **github**). These are some other parameters this command supported:

```bash
  -i, --issue:
      open given issue of the repository.
      # pigit open -- -i 20
      # pigit open -- --issue=20
  -c, --commit:
      open the current commit in the repo website.
      # pigit open -- --commit
  -p, --print:
      only print the url at the terminal, but don't open it.
  <branch>:
      open the page for this branch on the repo website.
```

## Alias

Alias is recommended for faster use _pigit_. Open your shell profile and append:

```bash
alias g=pigit
```

Then, you can use `g` to call pigit.

## Configuration

You can use `pigit --create-config` to create a template configuration at **pigit** home path.

On Linux or MacOS: `~/.config/pigit`

On windows should be: `C:\\User\\<your username>`

[here](./docs/pigit.conf) is a configuration template.

## Extra cmds

You can setting your custom cmds. It need create a `extra_cmds.py` file at the **pigit** home. And writing like this:

```python
import os

def print_user(args):
    print(os.system('whoami'))

extra_cmds = {
    'echo': {
        'command': 'echo 123',
    },
    'print-user': {
        'command': print_user,
        'type': 'func',
        'help': 'print system user name.'
    }
}
```

The `extra_cmds` dict is must. And the structure is command key and command info.

The command info has some options:

- `command`: (Must have) Short life corresponds to the complete command or a method. If it is a method, it must receive a parameter tuple.
- `type`: (Option) Mark the type of command, support ['func', 'command'], and the default is 'command'.
- `help`: (Option) Command help message.
- `has_arguments`: (Option, bool) Whether the command accepts parameters. Default is True.

## Feature

- Short command for quick use Git.
- Support custom your short command.
- Support command correction.
- Support simple command line GUI interaction.
- Support generate shell completion script.
- Support create `.gitignore` template from internet.
- Support code counter.
- Support quick open remote url (only support github).
- Have log output and help message tips.
- Support beautiful output.

---

LICENSE: [MIT](./LICENSE)
