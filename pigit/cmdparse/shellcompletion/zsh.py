# -*- coding:utf-8 -*-

from typing import Dict, List
import os
import textwrap

from .base import ShellCompletion

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

%(tools)s

%(func_name)s(){
  local curcontext="$curcontext" state line ret=1
  typeset -A opt_args

  %(arguments)s
  %(cases)s

  return ret
}

compdef %(func_name)s %(prog)s
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

    _SHELL: str = "zsh"

    try:
        _INJECT_PATH: str = os.environ["HOME"] + "/.zshrc"
    except:
        _INJECT_PATH: str = ""

    _template_source: str = _TEMPLATE_ZSH

    def _process_arguments(self, _arguments) -> str:
        res = []

        for one in _arguments:
            names = one[0].split()
            # help msg not allow include `[]`
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
        self, _sub_opts: Dict, _sub_opt_comps: List, relationship: List, idx: int = 1
    ):
        relation_str = ""

        for opt_name, opt_args in _sub_opts.items():
            _a = opt_args.get("_arguments", [])
            _a = self._process_arguments(_a)

            _s = []
            if _sub_c := opt_args.get("_sub_opts"):
                for n, x in _sub_c.items():
                    if help_str := x.get("help"):
                        # help msg not allow include `[]`
                        help_str = help_str.replace("[", "`").replace("]", "`")
                        _s.append(
                            f"'{n}[{help_str}]' \\",
                        )
                self._process_sub_commands(
                    _sub_c, _sub_opt_comps, relationship, idx + 1
                )
            if _a or _s:
                _sub_opt_comps.append(
                    _TEMP_V % (opt_name, textwrap.indent("\n".join([*_a, *_s]), "    "))
                )
                relation_str += f"    {opt_name}) __{opt_name}_values ;;\n"

        if relation_str:
            relation_str = (
                textwrap.dedent(
                    """
                    if [[ ${#line} -eq %s ]]; then
                      case $line[%s] in
                    %s
                      esac
                    fi
                    """
                )
                % (idx + 1, idx, relation_str)
            )
            relationship.append(relation_str)

    def args2complete(self, args_dict: Dict) -> str:
        prog_handle: str = args_dict["prog"]
        args: Dict = args_dict["args"]

        _arguments, _positions, _sub_opts = self._parse(args)

        # Generate zsh comp `_arguments` string.
        _arguments = self._process_arguments(_arguments)

        _sub_opt_str = ""
        _sub_sub_opt_comps = []
        _sub_relationship = []

        if _sub_opts:
            _subs = [
                f"'{opt_name}[{opt_args['help']}]' \\"
                for opt_name, opt_args in _sub_opts.items()
            ]

            _sub_opt_str = textwrap.dedent(
                """
                ######################
                # sub-commands helper
                ######################
                """
            ) + _TEMP_V % (
                "sub_opt",
                textwrap.indent("\n".join(_subs), "    "),
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

        return self._template_source % {
            "func_name": self.func_name,
            "prog": self.prog_name,
            "tools": "\n".join([*_sub_sub_opt_comps, _sub_opt_str]),
            "arguments": textwrap.indent(arguments_str, " " * 2),
            "cases": textwrap.indent(_opt_case_str, " " * 2),
        }

    def generate_resource(self) -> str:
        return self.args2complete(self.complete_vars)
