"""
Module: pigit/cmdparse/completion/bash.py
Description: Bash shell completion with git-aware argument completion.
Author: Zev
Date: 2026-04-12
"""

from __future__ import annotations

import textwrap

from .base import ShellCompletion
from .widgets import WIDGETS
from ...const import REPOS_PATH

# Git helper functions for bash completion
BASH_HELPERS = {
    "branch": '_git_branches() { git branch -a 2>/dev/null | sed "s/^[\\* ]*//" | sed "s|^remotes/||" | sort -u; }',
    "file": '_git_files() { { git status --porcelain 2>/dev/null | cut -c4- | grep -v "^$"; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u; }',
    "remote": "_git_remotes() { git remote 2>/dev/null | sort -u; }",
    "tag": "_git_tags() { git tag 2>/dev/null | sort -u; }",
    "commit": '_git_commits() { git log --oneline 2>/dev/null | cut -d" " -f1; }',
    "stash": '_git_stashes() { git stash list 2>/dev/null | cut -d":" -f1; }',
    "ref": '_git_refs() { git for-each-ref --format="%(refname:short)" 2>/dev/null | sort -u; }',
}

_BASH_TEMPLATE: str = textwrap.dedent("""\
    #!/usr/bin/env bash
    # PIGIT shell completion script
    # Generated for bash

    # Git helper functions for completion
    %(helper_functions)s

    # Main completion function
    %(func_name)s() {
        local cur prev words cword

        # Initialize completion variables (compatible with/without bash-completion)
        if type _init_completion &>/dev/null; then
            _init_completion || return
        else
            cur="${COMP_WORDS[COMP_CWORD]}"
            prev="${COMP_WORDS[COMP_CWORD-1]}"
            words=("${COMP_WORDS[@]}")
            cword=$COMP_CWORD
        fi

        # Find cmd / repo position
        local cmd_depth=0
        local repo_depth=0
        for ((i=1; i < cword; i++)); do
            if [[ "${words[i]}" == "cmd" ]]; then
                cmd_depth=$i
                break
            fi
            if [[ "${words[i]}" == "repo" ]]; then
                repo_depth=$i
                break
            fi
        done

        # Handle cmd subcommand completion with git-aware arguments
        if [[ $cmd_depth -gt 0 ]]; then
            local subcmd=""
            # Find subcommand after cmd
            for ((i=cmd_depth+1; i < cword; i++)); do
                if [[ "${words[i]}" != -* ]]; then
                    subcmd="${words[i]}"
                    break
                fi
            done

            # Complete subcommand name or its arguments
            if [[ -z "$subcmd" || "$subcmd" == "$cur" && "$cur" != -* ]]; then
                COMPREPLY=($(compgen -W "%(cmd_commands)s" -- "$cur"))
                return 0
            fi

            case "$subcmd" in
%(cmd_arg_cases)s
                *)
                    COMPREPLY=()
                    ;;
            esac
            return 0
        fi

        # Handle repo subcommand completion with repos-aware arguments
        if [[ $repo_depth -gt 0 ]]; then
            local subcmd=""
            for ((i=repo_depth+1; i < cword; i++)); do
                if [[ "${words[i]}" != -* ]]; then
                    subcmd="${words[i]}"
                    break
                fi
            done

            if [[ -z "$subcmd" || "$subcmd" == "$cur" && "$cur" != -* ]]; then
                COMPREPLY=($(compgen -W "%(repo_commands)s" -- "$cur"))
                return 0
            fi

            case "$subcmd" in
%(repo_arg_cases)s
                *)
                    COMPREPLY=()
                    ;;
            esac
            return 0
        fi

        # Handle top-level completion
        local first_word=""
        for ((i=1; i < cword; i++)); do
            if [[ "${words[i]}" != -* ]]; then
                first_word="${words[i]}"
                break
            fi
        done

        case "$first_word" in
            *)
                case "$cur" in
                    -*)
                        COMPREPLY=($(compgen -W "%(top_options)s" -- "$cur"))
                        ;;
                    *)
                        COMPREPLY=($(compgen -W "%(top_commands)s" -- "$cur"))
                        ;;
                esac
                ;;
        esac
    }

    complete -F %(func_name)s %(prop)s

%(widget)s
    """)


class BashCompletion(ShellCompletion):
    """Bash shell completion generator with enhanced git-aware completion."""

    SHELL: str = "bash"
    TEMPLATE_SRC: str = _BASH_TEMPLATE

    def _escape_case_pattern(self, pattern: str) -> str:
        """Escape case statement patterns to prevent wildcard matching.

        For example: b.o contains '.' which is a bash wildcard, must be quoted as "b.o"

        Args:
            pattern: The command pattern to escape.

        Returns:
            Escaped pattern with quotes if it contains special characters.
        """
        # Characters that have special meaning in bash case patterns
        special_chars = set(".?*[]!")
        if any(c in pattern for c in special_chars):
            return f'"{pattern}"'
        return pattern

    def _generate_helpers(self, used_completions: set) -> str:
        """Generate helper function definitions for git completion.

        Args:
            used_completions: Set of completion types used in commands.

        Returns:
            String containing helper function definitions.
        """
        if not used_completions:
            return ""
        helpers = []
        for comp in used_completions:
            if comp == "repos":
                helpers.append(
                    '_pigit_repos() { python3 -c \'import json,os; p=os.path.expanduser("%s");'
                    ' d=json.load(open(p)) if os.path.isfile(p) else {}; [print(k) for k in d]\''
                    ' 2>/dev/null; }' % REPOS_PATH
                )
            elif comp in BASH_HELPERS:
                helpers.append(BASH_HELPERS[comp])
        return "\n\n".join(helpers) + "\n"

    def _build_arg_cases(
        self, sub_args: dict, used_completions: set
    ) -> tuple[list[str], list[str]]:
        """Build command list and case arms for a sub-parser's arg_completion."""
        commands = []
        cases = []
        for cmd_name, cmd_info in sub_args.items():
            if not cmd_name.startswith("-") and cmd_name != "args":
                commands.append(cmd_name)
                arg_comp = ShellCompletion._promote_arg_completion(cmd_info)
                if arg_comp and arg_comp in self.GIT_COMPLETION_FUNCS:
                    used_completions.add(arg_comp)
                    helper_func = self.GIT_COMPLETION_FUNCS[arg_comp]
                    escaped_pattern = self._escape_case_pattern(cmd_name)
                    cases.append(
                        f"""                    {escaped_pattern})
                        COMPREPLY=($({helper_func} | grep -i "^$cur" 2>/dev/null))
                        ;;"""
                    )
        return commands, cases

    def generate_content(self) -> dict[str, str]:
        """Generate template variables for bash completion.

        Returns:
            Dict with template variables for the completion script.
        """
        comp_vars = self.complete_vars
        args = comp_vars.get("args", {})
        used_completions: set[str] = set()

        cmd_commands, cmd_arg_cases = self._build_arg_cases(
            args.get("cmd", {}).get("args", {}), used_completions
        )
        repo_commands, repo_arg_cases = self._build_arg_cases(
            args.get("repo", {}).get("args", {}), used_completions
        )

        top_options = []
        top_commands = []
        for name, prop in args.items():
            if name.startswith("-"):
                top_options.append(name.split()[0])
            else:
                top_commands.append(name)

        return {
            "helper_functions": self._generate_helpers(used_completions),
            "func_name": self.func_name,
            "prop": self.prog_name,
            "cmd_commands": " ".join(sorted(cmd_commands)),
            "cmd_arg_cases": "\n".join(cmd_arg_cases),
            "repo_commands": " ".join(sorted(repo_commands)),
            "repo_arg_cases": "\n".join(repo_arg_cases),
            "top_options": " ".join(sorted(top_options)),
            "top_commands": " ".join(sorted(top_commands)),
            "widget": WIDGETS["bash"],
        }

    def generate_resource(self) -> str:
        """Generate completion script.

        Returns:
            Complete bash completion script as string.
        """
        content_vars = self.generate_content()
        return self.TEMPLATE_SRC % content_vars
