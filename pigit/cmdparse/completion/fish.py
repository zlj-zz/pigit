# -*- coding:utf-8 -*-

import textwrap

from .base import ShellCompletion


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
        """
    )

    # TODO:improve `fish` completion script.
