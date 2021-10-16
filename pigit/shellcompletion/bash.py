# -*- coding:utf-8 -*-

import os
import textwrap

from .base import ShellCompletion


class BashCompletion(ShellCompletion):

    _SHELL: str = "bash"

    _INJECT_PATH: str = os.environ["HOME"] + "/.bashrc"

    _TEMPLATE: str = textwrap.dedent(
        """\
        #!/usr/env bash

        _complete_%(prop)s(){
          if [[ "${COMP_CWORD}" == "1" ]];then
              COMP_WORD="%(complete_vars)s"
              COMPREPLY=($(compgen -W "$COMP_WORD" -- ${COMP_WORDS[${COMP_CWORD}]}))
          fi
        }

        complete -F _complete_%(prop)s %(prop)s
        """
    )

    def generate(self):
        return " ".join(self.complete_vars.keys())
