# -*- coding:utf-8 -*-

import os
import textwrap

from .base import ShellCompletion


class ZshCompletion(ShellCompletion):

    _SHELL: str = "zsh"

    _INJECT_PATH: str = os.environ["HOME"] + "/.zshrc"

    _TEMPLATE: str = textwrap.dedent(
        """\
        #compdef %(prop)s

        complete_%(prop)s(){
        local curcontext="$curcontext" state line ret=1
        typeset -A opt_args

        _alternative\\
          \'args:options arg:((\\
            %(complete_vars)s
          ))\'\\
          'files:filename:_files'
        return ret
        }

        compdef complete_%(prop)s %(prop)s
        """
    )

    def generate(self):
        vars = []

        for k, desc in self.complete_vars.items():
            if not desc:
                desc = "no description."
            vars.append('    {0}\\:"{1}"\\'.format(k, desc))

        return ("\n".join(vars)).strip()
