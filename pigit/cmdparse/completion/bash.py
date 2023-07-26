# -*- coding:utf-8 -*-

import textwrap

from .base import ShellCompletion


class BashCompletion(ShellCompletion):
    SHELL: str = "bash"

    TEMPLATE_SRC: str = textwrap.dedent(
        """\
        #!/usr/env bash

        %(func_name)s(){
          if [[ "${COMP_CWORD}" == "1" ]];then
              COMP_WORD="%(complete_vars)s"
              COMPREPLY=($(compgen -W "$COMP_WORD" -- ${COMP_WORDS[${COMP_CWORD}]}))
          fi
        }

        complete -F %(func_name)s %(prop)s
        """
    )

    # TODO:improve `bash` completion script.
