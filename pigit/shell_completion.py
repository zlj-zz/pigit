# -*- coding:utf-8 -*-

from __future__ import print_function
import os
import re
import textwrap

from .utils import run_cmd, exec_cmd


class ShellCompletionError(Exception):
    """ShellCompletion error class."""

    pass


class ShellCompletion(object):
    """Implement and inject help classes for completion scripts.

    Attributes:
        _TEMPLATE_ZSH (str): zsh completion template.
        _TEMPLATE_BASH (str): bash completion template.
        _TEMPLATE_FISH (str): fish completion template.
        Supported_Shell (list): supported shell list.
    """

    # The completion items each line muse be:
    #   -C\:"Add shell prompt script and exit.(Supported `bash`, `zsh`)"\\
    _TEMPLATE_ZSH = textwrap.dedent(
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

    _TEMPLATE_BASH = textwrap.dedent(
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

    _TEMPLATE_FISH = textwrap.dedent(
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

    Supported_Shell = ["zsh", "bash", "fish"]

    def __init__(self, prop, complete_vars, script_dir, shell=None, script_name=None):
        """Initialization.

        Args:
            complete_var (dict): complete arguments dict.
                >>> complete_vars = {
                ...     '-h': 'Display help messages',
                ...     '-v': 'Show version and exit',
                ... }
            script_dir (str): where is the completion file save.
            shell (str, optional): shell type. Defaults to None.
            script_name (str, optional): completion file name. Defaults to None.
            argparse_obj (ArgumentParser, optional): argparse.ArgumentParser. Defaults to None.

        Raises:
            TypeError: when `complete_var` is not dict.
        """
        super(ShellCompletion, self).__init__()

        self.prop = prop
        if not isinstance(complete_vars, dict):
            raise TypeError("complete_var muse be dict.")
        self.complete_vars = complete_vars
        self.script_dir = script_dir
        if not shell:
            shell = self.get_current_shell()
        elif shell.strip() not in self.Supported_Shell:
            raise ValueError(
                "shell name '{}' is not supported, see {}".format(
                    shell, self.Supported_Shell
                )
            )
        self.shell = shell
        self.scirpt_name = script_name
        # print(self.complete_var)

    @staticmethod
    def get_current_shell():
        """Gets the currently used shell.

        Returns:
            (str): Current shell string.
        """
        current_shell = ""
        _, resp = exec_cmd("echo $SHELL")
        if resp:
            current_shell = resp.split("/")[-1].strip()
        return current_shell.lower()

    def generate_resource(self):
        """Generate completion scirpt.

        Generate the completion script of the corresponding shell according to
        the template.

        Args:
            shell (str): Current used shell.

        Returns:
            (str): completion file name.
            (str): completion source.
            (str): shell config path.
        """

        if self.shell == "zsh":
            script_name = "zsh_comp"
            template = self._TEMPLATE_ZSH

            def gen_completion():
                vars = []

                for k, desc in self.complete_vars.items():
                    if not desc:
                        desc = "no description."
                    vars.append('    {}\\:"{}"\\'.format(k, desc))

                return ("\n".join(vars)).strip()

        elif self.shell == "bash":
            script_name = "bash_comp"
            template = self._TEMPLATE_BASH

            def gen_completion():
                return " ".join(self.complete_vars.keys())

        elif self.shell == "fish":
            script_name = "fish_comp"
            template = self._TEMPLATE_FISH

            def gen_completion():
                return " ".join(self.complete_vars.keys())

        if self.scirpt_name:
            script_name = self.scirpt_name
        complete_content = gen_completion()
        script_src = template % {"prop": self.prop, "complete_vars": complete_content}

        return script_name, script_src

    def write_completion(self, script_name, complete_src):
        """Save completion to config path.

        Args:
            name (str): completion name.
            complete_src (str): completion source.

        Returns:
            (str): completion full path.
        """

        if not os.path.isdir(self.script_dir):
            os.makedirs(self.script_dir, exist_ok=True)
        full_path = os.path.join(self.script_dir, script_name)
        try:
            with open(full_path, "w" if os.path.isfile(full_path) else "x") as f:
                for line in complete_src:
                    f.write(line)
            return True
        except Exception:
            return None

    def inject_into_shell(self, script_name):
        """Try using completion script.

        Inject the load of completion script into the configuration of shell.
        If it exists in the configuration, the injection will not be repeated.
        """
        # get shell config path
        _home_ = os.environ["HOME"]
        if self.shell == "zsh":
            config_path = _home_ + "/.zshrc"
        elif self.shell == "bash":
            config_path = _home_ + "/.bashrc"
        elif self.shell == "fish":
            config_path = _home_ + "/.config/fish/config.fish"

        full_script_path = os.path.join(self.script_dir, script_name)
        try:
            with open(config_path) as f:
                shell_conf = f.read()
                _re = re.compile(r"{}[^\s]*".format(full_script_path))
                files = _re.findall(shell_conf)
        except Exception as e:
            raise ShellCompletionError("Read shell config error: {}".format(e))

        has_injected = False
        # print(files)
        if files:
            has_injected = True

        if not has_injected:
            try:
                run_cmd('echo "source %s" >> %s ' % (full_script_path, config_path))
            except Exception as e:
                raise ShellCompletionError("Inject error: {}".format(e))
            return True
        else:
            return False

    def complete_and_use(self):
        """Add completion prompt script."""

        print("\nTry to add completion ...")

        current_shell = self.shell
        print("Detected shell: %s" % current_shell)

        if current_shell in self.Supported_Shell:
            script_name, completion_src = self.generate_resource()
            if self.write_completion(script_name, completion_src):
                try:
                    injected = self.inject_into_shell(script_name)
                    if injected:
                        print("Source your shell configuration.")
                    else:
                        print("Command already exist.")
                except Exception as e:
                    print(e)
            else:
                print("Write completion script failed.")
        else:
            print("Don't support completion of %s" % current_shell)


def process_argparse(argparse_obj):
    arguments = {}
    for action in argparse_obj.__dict__["_actions"]:
        for option in action.option_strings:
            arguments[option] = action.help
    return arguments
