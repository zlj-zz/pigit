# -*- coding:utf-8 -*-

from typing import Dict
import os
import textwrap

from .base import ShellCompletion


class BashCompletion(ShellCompletion):

    _SHELL: str = "bash"

    try:
        _INJECT_PATH: str = os.environ["HOME"] + "/.bashrc"
    except:
        _INJECT_PATH: str = ""

    _template_source: str = textwrap.dedent(
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

    def generate(self) -> str:
        # TODO:improve `bash` completion script.
        comp_keys = []

        _arguments, _positions, _sub_opts = self._parse(self.complete_vars["args"])

        for x in _arguments:
            comp_keys.extend(x[0].split())

        sub_q = [_sub_opts]
        while sub_q:
            temp: Dict = sub_q.pop(0)
            for opt_name, p in temp.items():
                comp_keys.append(opt_name)

                if _a := p.get("_arguments"):
                    for x in _a:
                        comp_keys.extend(x[0].split())
                if _opts := p.get("_sub_opts"):
                    sub_q.insert(-1, _opts)

        return " ".join(comp_keys)
