# PIGIT

![Python 3](https://img.shields.io/badge/Python-v3.8%5E-green?logo=python)
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

You can run `pigit -r` in terminal, and you will see this intro:

```
 ____ ___ ____ ___ _____
|  _ \_ _/ ___|_ _|_   _|
| |_) | | |  _ | |  | |
|  __/| | |_| || |  | |
|_|  |___\____|___| |_| version: 1.5.0-dev.1

git version 2.32.0 (Apple Git-132)

Local path: /opt/homebrew/lib/python3.9/site-packages/pigit-1.5.0.dev1-py3.9.egg/pigit

Description:
  Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.
  The open source path on github: https://github.com/zlj-zz/pigit.git

You can use -h or --help to get help and usage.

```

You can run `pigit -h` or `pigit --help` to get the help message. Like this:

```bash
usage: pigit [-h] [-v] [-r] [-f] [-i] [-d] [--out-log] [-c [PATH]] [-C] [--create-ignore TYPE]
             [--create-config]
             {cmd,repo} ...

Pigit TUI is called automatically if no parameters are followed.

positional arguments:
  {cmd,repo}
    cmd                 git short command.
    repo                repo options.
    open                open remote repository in web browser.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         Show version and exit.
  -r, --report          Report the pigit desc and exit.
  -f, --config          Display the config of current git repository and exit.
  -i, --information     Show some information about the current git repository.
  -d, --debug           Current runtime in debug mode.
  --out-log             Print log to console.

tools arguments:
  Auxiliary type commands.

  -c [PATH], --count [PATH]
                        Count the number of codes and output them in tabular form.A given path can be
                        accepted, and the default is the current directory.
  -C, --complete        Add shell prompt script and exit.(Supported bash, zsh, fish)
  --create-ignore TYPE  Create a demo .gitignore file. Need one argument, support: [android, c++, cpp, c,
                        dart, elisp, gitbook, go, java, kotlin, lua, maven, node, python, qt, r, ros, ruby,
                        rust, sass, swift, unity]
  --create-config       Create a pre-configured file of PIGIT.(If a profile exists, the values available in it
                        are used)
```

**For example**

You can use `pigit cmd -s` to check what short command it supported, it will display the corresponding help information and the original command, like this:

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
......
```

### Interaction

It support a simple interactive mode. You can use `pigit` into the interactive mode and it let control the working tree simpler. like this:

![interaction demo](./interaction.gif)

And in the interaction mode, you can use `?` or `h` to see the help message.

## Alias

Alias is good way to help you use _pigit_ faster . Open your shell profile and append:

```bash
if type pigit >/dev/null 2>&1; then
    alias gt=pigit
    alias g="pigit cmd"
fi
```

Then, you can use `gt` to call TUI and use `g` to call `pigit cmd`.

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

- Short command for quick use Git, and custom your short command.
- Provides command correction, when the command is wrong.
- Have a simple tui interaction, complete very troublesome operations.
- Code statistics and can be beautifully displayed.
- Support generate and use shell completion script.
- Support create `.gitignore` template from internet.
- Support quick open remote url (only support github).
- Have log output and help message tips.

---

LICENSE: [MIT](./LICENSE)
