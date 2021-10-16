# -*- coding:utf-8 -*-

import os
import textwrap

from .base import ShellCompletion


class FishCompletion(ShellCompletion):

    _SHELL: str = "fish"

    _INJECT_PATH: str = os.environ["HOME"] + "/.config/fish/config.fish"

    _TEMPLATE: str = textwrap.dedent(
        """\
        function complete_%(prop)s;
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
        "(complete_%(prop)s)";
        """
    )

    def generate(self):
        return " ".join(self.complete_vars.keys())
