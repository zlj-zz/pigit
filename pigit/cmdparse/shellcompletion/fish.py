# -*- coding:utf-8 -*-

from typing import Dict
import os
import textwrap

from .base import ShellCompletion


class FishCompletion(ShellCompletion):

    _SHELL: str = "fish"

    try:
        _INJECT_PATH: str = os.environ["HOME"] + "/.config/fish/config.fish"
    except:
        _INJECT_PATH: str = ""

    _template_source: str = textwrap.dedent(
        """\
        function %(func_name)s;
            set -l response;

            for value in (env %(complete_vars)s=fish_complete COMP_WORDS=(commandline -cp) \
        COMP_CWORD=(commandline -t) %(prop)s);
                set response $response $value;
            end;

            for completion in $response;
                set -l metadata (string split "," $completion);

                if test $metadata[1] = "dir";
                    __fish_complete_directories $metadata[2];
                else if test $metadata[1] = "file";
                    __fish_complete_path $metadata[2];
                else if test $metadata[1] = "plain";
                    print $metadata[2];
                end;
            end;
        end;

        complete --no-files --command %(prop)s --arguments \
        "(%(func_name)s)";
        """
    )

    def generate(self) -> str:
        # TODO:improve `fish` completion script.
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
