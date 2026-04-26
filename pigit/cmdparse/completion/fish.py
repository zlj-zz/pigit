# -*- coding: utf-8 -*-
"""
Module: pigit/cmdparse/completion/fish.py
Description: Fish shell completion generator.
Author: Zev
Date: 2026-04-15
"""

import textwrap

from .base import ShellCompletion
from .widgets import WIDGETS


class FishCompletion(ShellCompletion):
    SHELL: str = "fish"

    TEMPLATE_SRC: str = textwrap.dedent(
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

%(widget)s
        """
    )

    # TODO:improve `fish` completion script.

    def generate_resource(self) -> str:
        complete_content = self.generate_content()
        return self.TEMPLATE_SRC % {
            "func_name": self.func_name,
            "prop": self.prog_name,
            "complete_vars": complete_content,
            "widget": WIDGETS["fish"],
        }
