# pygittools

A terminal tool for git. When we use git, do you feel very uncomfortable with too long commands. For example: `git status --short`, this project can help you improve it. This project is written in Python. Now most UNIX like systems come with Python. So you can easily install and use it.

## Installation

### Pip

```bash
pip install -U pygittools
```

### Source

```bash
git clone https://github.com/zlj-zz/pygittools.git
cd pygittools
make install
```

## Usage

You can run `g` in terminal, and you will see this:

```
[git-tools] version: 1.0.2-beta
git version 2.30.1 (Apple Git-130)

Path: /opt/homebrew/lib/python3.9/site-packages/pygittools-1.0.2b0-py3.9.egg/pygittools/__init__.py

Description:
  Terminal tool, help you use git more simple. Support Linux and MacOS.
  It use short command to replace the original command, like:
  `g ws` -> `git status --short`, `g b` -> `git branch`.
  Also you use `g -s` to get the all short command, have fun and good lucky.
  The open source path: https://github.com/zlj-zz/pygittools.git

You can use -h and --help to get help and more usage.

```

You can run `g -h` or `g --help` to get the help message.

```bash
usage: g [-h] [-c] [-s] [-S TYPE] [-t] [-f] [-i] [-v] [--debug] [--out-log] [command] [args ...]

If you want to use some original git commands, please use -- to indicate.

positional arguments:
  command               Short git command.
  args                  Command parameter list.

optional arguments:
  -h, --help            show this help message and exit
  -c, --complete        Add shell prompt script and exit.(Supported `bash`, `zsh`)
  -s, --show-commands   List all available short command and wealth and exit.
  -S TYPE, --show-command TYPE
                        According to given type list available short command and wealth and exit.
  -t, --types           List all command types and exit.
  -f, --config          Display the config of current git repository and exit.
  -i, --information     Show some information about the current git repository.
  -v, --version         Show version and exit.
  --debug               Run in debug mode.
  --out-log             Print log to console.
```
