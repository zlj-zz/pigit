# -*- coding: utf-8 -*-
"""
Module: pigit/cmdparse/completion/zsh.py
Description: Zsh shell completion with git-aware argument completion.
Author: Zev
Date: 2026-04-12
"""

import textwrap

from .base import ShellCompletion
from .widgets import WIDGETS

# Git helper functions for zsh
ZSH_HELPERS = {
    "branch": """\
_git_branches() {
    local -a branches
    branches=(${(f)"$(git branch -a 2>/dev/null | sed 's/^[\\* ]*//' | sed 's|^remotes/||' | sort -u)"})
    (( $#branches )) && compadd -a branches
}""",
    "file": """\
_git_files() {
    local -a files
    files=(${(f)"$(git ls-files 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null | sort -u)"})
    (( $#files )) && compadd -a files
}""",
    "remote": """\
_git_remotes() {
    local -a remotes
    remotes=(${(f)"$(git remote 2>/dev/null | sort -u)"})
    (( $#remotes )) && compadd -a remotes
}""",
    "tag": """\
_git_tags() {
    local -a tags
    tags=(${(f)"$(git tag 2>/dev/null | sort -u)"})
    (( $#tags )) && compadd -a tags
}""",
    "commit": """\
_git_commits() {
    local -a commits
    commits=(${(f)"$(git log --oneline 2>/dev/null | cut -d' ' -f1)"})
    (( $#commits )) && compadd -a commits
}""",
    "stash": """\
_git_stashes() {
    local -a stashes
    stashes=(${(f)"$(git stash list 2>/dev/null | cut -d':' -f1)"})
    (( $#stashes )) && compadd -a stashes
}""",
    "ref": """\
_git_refs() {
    local -a refs
    refs=(${(f)"$(git for-each-ref --format='%(refname:short)' 2>/dev/null | sort -u)"})
    (( $#refs )) && compadd -a refs
}""",
}

_TEMPLATE_ZSH: str = """\
#compdef %(prog)s

#--------------------------------------------------------------------
# This completion script is generated automatically by parsing
# parameters.
#
#--------------------------------------------------------------------
# Author
#--------
#
# * Zachary Zhang (https://github.com/zlj-zz)
#
#--------------------------------------------------------------------

%(git_helpers)s

%(tools)s

%(func_name)s(){
  local curcontext="$curcontext" state line ret=1
  typeset -A opt_args

  %(arguments)s
  %(cases)s

  return ret
}

compdef %(func_name)s %(prog)s

%(widget)s
"""

_TEMP_A: str = """
_arguments -C \\
%s
&& ret=0

"""

_TEMP_V: str = """\
__%s_values() {
  _values '' \\
%s
  && ret=0
}
"""


class ZshCompletion(ShellCompletion):
    SHELL: str = "zsh"

    TEMPLATE_SRC: str = _TEMPLATE_ZSH

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._used_git_helpers: set[str] = set()

    def _get_zsh_completion_func(self, comp_type: str) -> str:
        """Get zsh completion function for a completion type."""
        completion_map = {
            "branch": "_git_branches",
            "file": "_path_files -/",
            "remote": "_git_remotes",
            "tag": "_git_tags",
            "commit": "_git_commits",
            "stash": "_git_stashes",
            "ref": "_git_refs",
        }
        return completion_map.get(comp_type, "")

    def _process_arguments(self, _arguments) -> list[str]:
        res = []

        for one in _arguments:
            names = one[0].split()
            help_str = one[1].replace("[", "`").replace("]", "`")

            if len(names) == 1:
                res.append(f"'{one[0]}[{help_str}]' \\")
            else:
                res.append(
                    "{%(keys)s}'[%(desc)s]' \\"
                    % {"keys": ",".join(names), "desc": help_str}
                )

        return res

    def _process_sub_commands(
        self, _sub_opts: dict, _sub_opt_comps: list, relationship: list, idx: int = 1
    ):
        relation_str = ""
        arg_completion_cases = []

        for opt_name, opt_args in _sub_opts.items():
            _a = opt_args.get("_arguments", [])
            _a = self._process_arguments(_a)

            # Check if this subcommand has arg_completion
            arg_comp = opt_args.get("arg_completion", "")
            zsh_func = self._get_zsh_completion_func(arg_comp) if arg_comp else ""

            _s = []
            if _sub_c := opt_args.get("_sub_opts"):
                for n, x in _sub_c.items():
                    if help_str := x.get("help"):
                        help_str = help_str.replace("[", "`").replace("]", "`")
                        _s.append(f"'{n}[{help_str}]' \\")
                    if nested_arg_comp := x.get("arg_completion"):
                        nested_zsh_func = self._get_zsh_completion_func(nested_arg_comp)
                        if nested_zsh_func:
                            self._used_git_helpers.add(nested_arg_comp)
                self._process_sub_commands(
                    _sub_c, _sub_opt_comps, relationship, idx + 1
                )

            if zsh_func:
                # Has arg_completion - create case statement for it
                self._used_git_helpers.add(arg_comp)
                arg_completion_cases.append(f"    {opt_name}) {zsh_func} ;;")
            elif _a or _s:
                _sub_opt_comps.append(
                    _TEMP_V % (opt_name, textwrap.indent("\n".join([*_a, *_s]), "    "))
                )
                relation_str += f"    {opt_name}) __{opt_name}_values ;;\n"

        # Combine regular cases with arg_completion cases
        all_cases = relation_str + "\n".join(arg_completion_cases)

        if all_cases.strip():
            case_block = textwrap.dedent(
                """
                if [[ ${{#line}} -eq {depth} ]]; then
                  case $line[{idx}] in
                {cases}
                  esac
                fi
                """
            ).format(depth=idx + 1, idx=idx, cases=all_cases.rstrip())
            relationship.append(case_block)

    def _generate_git_helpers(self) -> str:
        """Generate git helper function definitions."""
        if not self._used_git_helpers:
            return ""
        helpers = [
            ZSH_HELPERS[comp] for comp in self._used_git_helpers if comp in ZSH_HELPERS
        ]
        return "\n\n".join(helpers) + "\n"

    def args2complete(self, args_dict: dict) -> str:
        prog_handle: str = args_dict["prog"]
        args: dict = args_dict["args"]

        _arguments, _positions, _sub_opts = self._parse(args)
        _arguments = self._process_arguments(_arguments)

        _sub_opt_str = ""
        _sub_sub_opt_comps = []
        _sub_relationship = []

        if _sub_opts:
            _subs = []
            for opt_name, opt_args in _sub_opts.items():
                help_str = opt_args.get("help", "").replace("[", "`").replace("]", "`")
                _subs.append(f"'{opt_name}[{help_str}]' \\")

            _sub_opt_str = (
                textwrap.dedent(
                    """
                    ######################
                    # sub-commands helper
                    ######################
                    """
                )
                + _TEMP_V % ("sub_opt", textwrap.indent("\n".join(_subs), "    "))
            )

            self._process_sub_commands(
                _sub_opts, _sub_sub_opt_comps, _sub_relationship, idx=1
            )

        _opt_case_str = ""

        if _sub_opt_str:
            _arguments.append("'1: :->opts'\\")
            _opt_case_str = textwrap.dedent(
                """
                case $state in
                opts) __sub_opt_values ;;
                """
            )

        if _sub_sub_opt_comps:
            _arguments.append("'*::arg:->args'\\")
            _opt_case_str += "  args)\n"
            _opt_case_str += textwrap.indent("\n".join(_sub_relationship), " " * 4)

        if _opt_case_str:
            _opt_case_str += "esac"

        arguments_str = _TEMP_A % textwrap.indent("\n".join(_arguments), " " * 2)

        return self.TEMPLATE_SRC % {
            "func_name": self.func_name,
            "prog": self.prog_name,
            "git_helpers": self._generate_git_helpers(),
            "tools": "\n".join([*_sub_sub_opt_comps, _sub_opt_str]),
            "arguments": textwrap.indent(arguments_str, " " * 2),
            "cases": textwrap.indent(_opt_case_str, " " * 2),
            "widget": WIDGETS["zsh"],
        }

    def generate_resource(self) -> str:
        return self.args2complete(self.complete_vars)
