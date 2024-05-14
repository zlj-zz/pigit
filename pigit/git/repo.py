# -*- coding:utf-8 -*-

import os
import re
import json
import textwrap
from typing import Dict, List, Optional, Tuple, Union, Generator
from collections import Counter
from pathlib import Path

from plenty.str_utils import shorten, byte_str2str
from plenty.console import Console

from pigit.ext.executor import SILENT, WAITING, REPLY, DECODE, Executor
from pigit.ext.log import logger
from pigit.ext.utils import adjudgment_type, get_file_icon
from .model import File, Commit, Branch


class RepoError(Exception):
    """Error class of ~GitOption."""


class Repo:
    """Git option class."""

    def __init__(
        self, path: Optional[str] = None, repo_json_path: Optional[str] = None
    ) -> None:
        """
        Args:
            path (Optional[str], optional): repo path. Defaults to None.
            repo_json_path (Optional[str], optional): repos info json path.
                Defaults to None.
        """
        self.executor = Executor()

        self.path = path
        self.repo_json_path = (
            Path("./repos.json") if repo_json_path is None else Path(repo_json_path)
        )

        # create repo path dir.
        self.repo_json_path.parent.mkdir(parents=True, exist_ok=True)

    def update_setting(
        self, *, op_path: Optional[str] = None, repo_info_path: Optional[str] = None
    ) -> "Repo":
        if op_path is not None:
            self.path = op_path
        if repo_info_path is not None:
            self.repo_json_path = Path(repo_info_path)

        return self

    # ==================
    # Basic info option
    # ==================
    def confirm_repo(
        self, given_path: Optional[str] = None, exclude_submodule: bool = False
    ) -> Tuple[str, str]:
        """Confirm given path whether a git repo. And return repo path info.
        Get the current git repository path. If not, the path is empty.
        Get the local git config path. If not, the path is empty.

        Returns:
            (tuple[str, str]): repository path, git config path.
        """
        path = given_path or self.path or "."
        path = os.path.abspath(path)

        repo_path: str = ""
        git_conf_path: str = ""

        if not os.path.isdir(path):
            return repo_path, git_conf_path

        _, err, repo_path = self.executor.exec(
            "git rev-parse --git-dir", flags=REPLY | DECODE, cwd=path
        )
        if err:
            return repo_path, git_conf_path

        # remove useless space.
        repo_path = repo_path.strip()

        if ".git/modules/" in repo_path and not exclude_submodule:
            # this repo is submodule.
            git_conf_path = repo_path
            repo_path = repo_path.replace(".git/modules/", "")
        elif repo_path == ".git":
            repo_path = path
            git_conf_path = os.path.join(repo_path, ".git")
        else:
            git_conf_path = repo_path
            repo_path = repo_path[:-5]

        return repo_path, git_conf_path

    def get_config(self, path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """Try to read git config and parse, return a config dict.

        Args:
            path (Optional[str], optional): repo path. Defaults to None.

        Returns:
            Dict[str, Dict[str, str]]: config dict.
        """
        path = path or self.path

        _, config_path = self.confirm_repo(path)
        try:
            with open(f"{config_path}/config", "r") as cf:
                context = cf.read()
        except Exception as e:
            logger(__name__).warning(f"Can not read config with: {e}")
            return {}
        else:
            conf_dict: Dict[str, Dict[str, str]] = {}
            conf_list = re.split(r"\r\n|\r|\n", context)
            config_type: str = ""

            for line in conf_list:
                line = line.strip()

                if not line:
                    continue

                elif line.startswith("["):
                    config_type = line[1:-1].strip()
                    conf_dict[config_type] = {}

                elif "=" in line:
                    key, value = line.split("=", 1)
                    conf_dict[config_type][key.strip()] = value.strip()

                else:
                    continue

            return conf_dict

    def get_head(self, path: Optional[str] = None) -> Optional[str]:
        """Get current repo head. Return a branch name or a commit sha string."""
        path = path or self.path

        _, _, head = self.executor.exec(
            "git symbolic-ref -q --short HEAD || git describe --tags --exact-match",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if head is not None:
            head = head.rstrip()
        return head

    def get_first_pushed_commit(
        self, path: Optional[str] = None, branch_name: Optional[str] = None
    ) -> str:
        path = path or self.path

        if branch_name is None:
            if head := self.get_head(path):
                branch_name = head
            else:
                return ""

        command = "git merge-base %s %s@{u}" % (branch_name, branch_name)
        _, _, commit_msg = self.executor.exec(command, flags=REPLY | DECODE, cwd=path)
        return commit_msg.strip()

    def get_branches(
        self,
        path: Optional[str] = None,
        include_remote: bool = False,
        plain: bool = True,
    ) -> List[str]:
        """Get repo all branch."""
        path = path or self.path

        include_all = "--all" if include_remote else ""
        color = "never" if plain else "always"

        _, _, res = self.executor.exec(
            f"git branch {include_all} --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        if res is None:
            return []
        return [branch[2:] for branch in res.rstrip().split("\n")]

    def get_remotes(self, path: Optional[str] = None) -> List[str]:
        """Get repo remote url."""

        # Get remote name, exit when error.
        path = path or self.path
        _, _, res = self.executor.exec(
            "git remote show", flags=REPLY | DECODE, cwd=path
        )

        return res.strip().split("\n") if res else []

    def get_remote_url(
        self, path: Optional[str] = None, remote_name: Optional[str] = None
    ) -> str:
        """Get repo remote url."""
        path = path or self.path

        if remote_name is None:
            if remotes := self.get_remotes(path):
                remote_name = remotes[0]
            else:
                return ""

        # Get remote url, exit when error.
        _, err, remote_url = self.executor.exec(
            f"git ls-remote --get-url {remote_name}", flags=REPLY | DECODE, cwd=path
        )

        if err:
            return ""

        remote_url = remote_url[:-5]
        return remote_url

    def get_summary(self, path: Optional[str] = None, plain: bool = True) -> str:
        path = path or self.path
        color = "never" if plain else "always"
        _, _, summary = self.executor.exec(
            f"git shortlog --summary --numbered --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        return summary

    def get_repo_desc(
        self,
        include_part: Optional[List] = None,
        path: Optional[str] = None,
        color: bool = True,
    ) -> str:
        """Return a string of repo various information.

        Args:
                include_part (Optional[list], optional): should return info part: [path,remote,branch,log,summary]. Defaults to None.
                path (Optional[str], optional): custom repo path. Defaults to None.
                color (bool, optional): whether return with color. Defaults to True.

        Returns:
                str: desc info.
        """
        path = path or self.path
        error_str = "`Error getting.`<error>"
        gen = ["[b`Repository Information`]" if color else "[Repository Information]"]
        repo_path, _ = self.confirm_repo(path)

        # Get content.
        if not include_part or "path" in include_part:
            gen.append(
                f"Repository: \n\t`{repo_path}`<sky_blue>\n"
                if color
                else f"Repository: \n\t{repo_path}\n"
            )

        # Get remote url.
        if not include_part or "remote" in include_part:
            try:
                with open(f"{repo_path}/.git/config", "r") as cf:
                    config = cf.read()
            except Exception:
                remote = error_str
            else:
                res = re.findall(r"url\s=\s(.*)", config)
                remote = "\n".join(
                    [f"\ti`{x}`<sky_blue>" if color else f"\t{x}" for x in res]
                )
            gen.append("Remote: \n%s\n" % remote)

        # Get all branches.
        if not include_part or "branch" in include_part:
            branches = self.get_branches(path, include_remote=True, plain=not color)
            branches_str = (
                "\n".join(f"\t{branch}" for branch in branches)
                if branches
                else f"\t{error_str}"
            )
            gen.append("Branches: \n%s\n" % branches_str)

        # Get the latest log.
        if not include_part or "log" in include_part:
            _, err, res = self.executor.exec(
                f"git log --stat --oneline --decorate -1 --color={'always' if color else 'never'}",
                flags=REPLY | DECODE,
                cwd=path,
            )
            git_log = "\t" + error_str if err else textwrap.indent(res, "\t")
            gen.append("Latest log:\n%s\n" % git_log)

        # FIXME: will broken in a init repo.
        # Get git summary.
        # if not include_part or "summary" in include_part:
        #     summary = self.get_summary(path, not color)
        #     gen.append("Summary:\n%s\n" % summary or error_str)

        return "\n".join(gen)

    # =============
    # Special info
    # =============
    def load_branches(self, path: Optional[str] = None) -> List[Branch]:
        path = path or self.path
        branches = []

        _, _, resp = self.executor.exec(
            "git branch --sort=-committerdate "
            '--format="%(HEAD)|%(refname:short)|%(upstream:short)|%(upstream:track)" ',
            flags=REPLY | DECODE,
            cwd=path,
        )
        resp = resp.strip()
        if not resp:
            return branches

        lines = resp.split("\n")

        for line in lines:
            items = line.split("|")
            branch = Branch(
                name=items[1], ahead="?", behind="?", is_head=items[0] == "*"
            )

            upstream_name = items[2]

            if not upstream_name:
                branches.append(branch)
                continue

            branch.upstream_name = upstream_name

            track = items[3]
            _re = re.compile(r"ahead (\d+)")
            branch.ahead = str(match[1]) if (match := _re.search(track)) else "0"
            _re = re.compile(r"behind (\d+)")
            branch.behind = str(match[1]) if (match := _re.search(track)) else "0"
            branches.append(branch)

        return branches

    def load_log(
        self,
        branch_name: str = "",
        limit: Optional[int] = None,
        filter_path: str = "",
        arg_str: str = '--oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" --abbrev=20 --date=unix',
        path: Optional[str] = None,
    ) -> str:
        path = path or self.path

        limit_flag = f"-{limit}" if limit else ""
        filter_flag = f"--follow -- {filter_path}" if filter_path else ""

        _, _, resp = self.executor.exec(
            f"git log {branch_name} {arg_str} {limit_flag} {filter_flag}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        return "" if resp is None else resp.strip()

    def load_status(
        self,
        max_width: int = 80,
        ident: int = 2,
        plain: bool = False,
        path: Optional[str] = None,
        icon: bool = False,
    ) -> List[File]:
        """Get the file tree status of GIT for processing and encapsulation.

        Args:
                max_width (int): The max length of display string.
                ident (int, option): Number of reserved blank characters in the header.

        Returns:
                (List[File]): Processed file status list.
        """
        path = path or self.path
        file_items = []

        _, err, files = self.executor.exec(
            "git status -s -u --porcelain", flags=REPLY | DECODE, cwd=path
        )
        if err:
            return file_items
        for file in files.rstrip().split("\n"):
            if not file.strip():
                # skip blank line.
                continue

            change = file[:2]
            staged_change = file[:1]
            unstaged_change = file[1:2]
            name = file[3:]
            if name.endswith('"'):
                # may is chinese char code.
                name = byte_str2str(name[1:-1])
            untracked = change in ["??", "A ", "AM"]
            has_no_staged_change = staged_change in [" ", "U", "?"]
            has_merged_conflicts = change in ["DD", "AA", "UU", "AU", "UA", "UD", "DU"]
            has_inline_merged_conflicts = change in ["UU", "AA"]

            display_name = shorten(name, max_width - 3 - ident)

            icon_str = get_file_icon(adjudgment_type(display_name)) if icon else ""

            # color full command.
            display_str = Console.render_str(
                f"`{staged_change}`<{'bad' if has_no_staged_change else'right'}>`{unstaged_change}`<{'bad' if unstaged_change!=' ' else'right'}> {icon_str}{display_name}"
            )

            file_ = File(
                name=name,
                display_str=file if plain else display_str,
                short_status=change,
                has_staged_change=not has_no_staged_change,
                has_unstaged_change=unstaged_change != " ",
                tracked=not untracked,
                deleted=unstaged_change == "D" or staged_change == "D",
                added=unstaged_change == "A" or untracked,
                has_merged_conflicts=has_merged_conflicts,
                has_inline_merged_conflicts=has_inline_merged_conflicts,
            )

            file_items.append(file_)

        return file_items

    def load_file_diff(
        self,
        file: str,
        tracked: bool = True,
        cached: bool = False,
        plain: bool = False,
        path: Optional[str] = None,
    ) -> str:
        """Gets the modification of the file.

        Args:
                file (str): file path relative to git.
                tracked (bool, optional): Defaults to True.
                cached (bool, optional): Defaults to False.
                plain (bool, optional): Whether need color. Defaults to False.

        Returns:
                (str): change string.
        """
        path = path or self.path

        _plain = "--color=never" if plain else "--color=always"
        _cached = "--cached" if cached else ""
        _tracked = "--" if tracked else "--no-index -- /dev/null"

        if "->" in file:  # rename status.
            file = file.split("->")[-1].strip()

        _, err, res = self.executor.exec(
            f"git diff --submodule --no-ext-diff {_plain} {_cached} {_tracked} {file}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        return "Can't get diff." if err else res.rstrip()

    def load_commits(
        self,
        branch_name: str,
        limit: bool = True,
        filter_path: str = "",
        path: Optional[str] = None,
    ) -> List[Commit]:
        """Get the all commit of a given branch.

        Args:
                branch_name (str): want branch name.
                limit (bool): Whether to get only the latest 300.
                filter_path (str): filter dir path, default is empty.
        """
        path = path or self.path

        first_pushed_commit = self.get_first_pushed_commit(path, branch_name)
        passed_first_pushed_commit = not first_pushed_commit

        commits: List[Commit] = []

        # Generate git command.
        limit_flag = "-300" if limit else ""
        filter_flag = f"--follow -- {filter_path}" if filter_path else ""
        command = f'git log {branch_name} --oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" {limit_flag} --abbrev=20 --date=unix {filter_flag}'

        _, err, resp = self.executor.exec(command, flags=REPLY | DECODE, cwd=path)
        if err:
            return commits  # current is empty list.

        # Process data.
        for line in resp.split("\n"):
            split_ = line.split("|")

            sha = split_[0]
            unix_timestamp = int(split_[1])
            author = split_[2]
            extra_info = (split_[3]).strip()
            # parent_hashes = split_[4]
            message = "|".join(split_[5:])

            tag = []
            if extra_info:
                _re = re.compile(r"tag: ([^,\\]+)")
                if match := _re.search(extra_info):
                    tag.append(match[1])

            if sha == first_pushed_commit:
                passed_first_pushed_commit = True
            status = {True: "unpushed", False: "pushed"}[not passed_first_pushed_commit]

            commit_ = Commit(
                sha=sha,
                msg=message,
                author=author,
                unix_timestamp=unix_timestamp,
                status=status,
                extra_info=extra_info,
                tag=tag,
            )
            commits.append(commit_)

        return commits

    def load_commit_info(
        self,
        commit_sha: str = "",
        file_name: str = "",
        plain: bool = False,
        path: Optional[str] = None,
    ) -> str:
        """Gets the change of a file or all in a given commit.
        Args:
                commit_sha: commit id.
                file_name: file name(include full path).
                plain: whether has color.
        """
        path = path or self.path
        color_str = "never" if plain else "always"

        _, _, resp = self.executor.exec(
            f"git show --color={color_str} {commit_sha} {file_name}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        return resp.rstrip()

    # ===============
    # Options of git
    # ===============
    def switch_file_status(self, file: File, path: Optional[str] = None):
        """Change the file stage status.

        Args:
            file (File): git file object.
            path (Optional[str], optional): exec path. Defaults to None.
        """
        path = path or self.path
        file_name = file.get_file_str()

        if file.has_merged_conflicts or file.has_inline_merged_conflicts:
            pass
        elif file.has_unstaged_change:
            self.executor.exec(
                f"git add -- '{file_name}'", flags=WAITING | SILENT, cwd=path
            )
        elif file.has_staged_change:
            if file.tracked:
                self.executor.exec(
                    f"git reset HEAD -- '{file_name}'",
                    flags=WAITING | SILENT,
                    cwd=path,
                )
            else:
                self.executor.exec(
                    f"git rm --cached --force -- '{file_name}'",
                    flags=WAITING | SILENT,
                    cwd=path,
                )

    def discard_file(
        self,
        file: Union[File, str],
        path: Optional[str] = None,
        tracked: Optional[bool] = None,
    ):
        path = path or self.path
        file_name = file.get_file_str()

        if tracked is None:
            if isinstance(file, File):
                tracked = file.tracked
            else:
                raise RepoError("Please set `tracked` or give a 'File'.") from None

        if tracked:
            self.executor.exec(f"git checkout -- {file_name}", cwd=path)
        else:
            os.remove(os.path.join(path or "", file_name))

    def ignore_file(self, file: Union[File, str], path: Optional[str] = None):
        """Append file to `.gitignore` file."""

        path = path or self.path
        repo_path, _ = self.confirm_repo(path)
        file_name = file.get_file_str()

        with open(f"{repo_path}/.gitignore", "a+") as f:
            f.write(f"\n{file_name}")

    def checkout_branch(self, branch_name: str, path: Optional[str] = None) -> str:
        path = path or self.path
        _, err, _ = self.executor.exec(f"git checkout {branch_name}", cwd=path)
        return err or "ok"

    def open_repo_in_browser(
        self,
        path: Optional[str] = None,
        branch: str = "",
        issue: str = "",
        commit: str = "",
        print: bool = False,
    ) -> Tuple[bool, str]:
        path = path or self.path
        remote_url = self.get_remote_url(path=path)

        if branch:
            branch = f"/tree/{branch}"
            remote_url += branch
        elif issue:
            issue = f"/issues/{issue}"
            remote_url += issue
        elif commit:
            commit = f"/commit/{commit}"
            remote_url += commit

        if print:
            return True, f"Remote URL: `{remote_url}`<sky_blue>"

        try:
            import webbrowser

            webbrowser.open(remote_url)
        except Exception as e:
            return False, f"Failed to open the repo; {e}"
        else:
            return True, "Successfully opened repo."

    # ====================
    # custom repos option
    # ====================
    @staticmethod
    def _make_repo_name(path: str, repos: Dict[str, str], name_counts: Counter) -> str:
        """
        Given a new repo `path`, create a repo name. By default, basename is used.
        If name collision exists, further include parent path name.

        Args:
            path (str): repo path.
            repos (list[str]): path list of exist repos.
            name_counts (Counter): generated default name.

        Returns:
            (str): final repo name.
        """

        name: str = os.path.basename(os.path.normpath(path))
        if name in repos or name_counts[name] > 1:
            # path has no trailing /
            par_name = os.path.basename(os.path.dirname(path))
            return os.path.join(par_name, name)
        return name

    def load_repos(self) -> Dict:
        """Load repos info from cache file."""

        if not self.repo_json_path.is_file():
            return {}

        with self.repo_json_path.open(mode="r") as fp:
            return json.load(fp)

    def dump_repos(self, repos: Dict) -> bool:
        """Dump repos info to cache file, re-write mode."""

        try:
            with self.repo_json_path.open(mode="w+") as fp:
                json.dump(repos, fp, indent=2)
                return True
        except Exception:
            return False

    def clear_repos(self) -> None:
        self.repo_json_path.unlink(missing_ok=True)

    def ll_repos(self, reverse: bool = False) -> Generator[List[Tuple], None, None]:
        exist_repos = self.load_repos()

        for repo_name, prop in exist_repos.items():
            repo_path = prop["path"]
            head = self.get_head(repo_path)

            # jump invalid repo.
            if head is None:
                if reverse:
                    yield [
                        (repo_name, ""),
                        ("Local Path", repo_path),
                    ]

            elif not reverse:
                _, _, unstaged = self.executor.exec(
                    "git diff --stat", flags=REPLY | DECODE, cwd=repo_path
                )
                _, _, staged = self.executor.exec(
                    "git diff --stat --cached", flags=REPLY | DECODE, cwd=repo_path
                )
                _, _, untracked = self.executor.exec(
                    "git ls-files -zo --exclude-standard",
                    flags=REPLY | DECODE,
                    cwd=repo_path,
                )
                commit_hash = self.get_first_pushed_commit(
                    path=repo_path, branch_name=head
                )
                commit = self.load_log(
                    limit=1,
                    arg_str="--format='%s (%cd)||%C(auto)%d%n' --date=relative --color",
                    path=repo_path,
                )

                commit_msg, branch_status = commit.strip().split("||")
                unstaged_symbol = "*" if unstaged else " "
                staged_symbol = "+" if staged else " "
                untracked_symbol = "?" if untracked else " "

                yield [
                    (repo_name, ""),
                    (
                        "Branch",
                        f"{head} {unstaged_symbol}{staged_symbol}{untracked_symbol}",
                    ),
                    ("Status", branch_status),
                    ("Commit Hash", commit_hash),
                    ("Commit Msg", commit_msg),
                    ("Local Path", repo_path),
                ]

    def add_repos(self, paths: List[str], dry_run: bool = False) -> List:
        """Traverse the incoming paths. If it is not saved and is a git
        directory, add it to repos.

        Args:
            paths (list[str]): incoming paths.
            dry_run (bool, optional): Show but not really execute. Defaults to False.
            silent (bool, optional): No output. Defaults to False.
        """

        exist_repos = self.load_repos()
        exist_paths = [r["path"] for r in exist_repos.values()]

        new_git_paths = []
        for path in paths:
            repo_path, _ = self.confirm_repo(path)
            if repo_path and repo_path not in exist_paths:
                new_git_paths.append(repo_path)

        if new_git_paths and not dry_run:
            name_counts = Counter(
                os.path.basename(os.path.normpath(p)) for p in new_git_paths
            )
            new_repos = {
                self._make_repo_name(path, exist_repos, name_counts): {"path": path}
                for path in new_git_paths
            }

            self.dump_repos({**exist_repos, **new_repos})

        return new_git_paths

    def rm_repos(self, repos: List[str], use_path: bool = False) -> List[Tuple]:
        exist_repos = self.load_repos()

        del_repos = []
        del_paths = []
        if use_path:
            del_repos.extend(
                repo for repo, info in exist_repos.items() if info["path"] in repos
            )
        else:
            del_repos.extend(repo for repo in repos if exist_repos.get(repo))

        for repo in del_repos:
            del_paths.append(exist_repos[repo]["path"])
            del exist_repos[repo]

        self.dump_repos(exist_repos)
        return list(zip(del_repos, del_paths))

    def rename_repo(self, repo: str, name: str) -> Tuple[bool, str]:
        """Rename repo

        Args:
            repo (str): exist repo name
            name (str): new name

        Returns:
            Tuple[bool, str]: whether rename successful, tip msg.
        """

        exist_repos = self.load_repos()

        if name == repo:
            return False, "The same name do nothing!"
        elif name in exist_repos:
            return False, f"'{name}' is already in use!"
        elif repo not in exist_repos:
            return False, f"'{repo}' is not a valid repo name!"
        else:
            prop = exist_repos[repo]
            del exist_repos[repo]
            exist_repos[name] = prop

            self.dump_repos(exist_repos)
            return True, f"rename successful, `{repo}`->`{name}`."

    def cd_repo(self, repo: Optional[str] = None):
        """Quick jump to repo dir.

        Args:
            repo (Optional[str], optional): repo name. Defaults to None.

        Returns:
            _type_: _description_
        """

        command = "$SHELL -c 'cd {0} && exec $SHELL'"
        exist_repos = self.load_repos()

        if repo in exist_repos:
            path = exist_repos[repo]["path"]
            self.executor.exec(command.format(path), flags=WAITING)
        else:
            cur_cache = []
            print("Managed repos include the following:")
            for i, r in enumerate(exist_repos, 0):
                cur_cache.append(r)
                print(".  ", i, r)

            try:
                input_num = int(input("Please input the index:"))
                if 0 <= input_num <= len(cur_cache):
                    path = exist_repos[cur_cache[input_num]]["path"]
                    print(self.executor.exec(command.format(path), cwd=".", flags=WAITING))
                else:
                    print("Error: index out of range.")
            except Exception:
                print("Error: index need input a number.")

    def process_repos_option(self, repos: Optional[List[str]], cmd: str):
        exist_repos = self.load_repos()
        print(f":: {cmd}\n")

        if repos:
            exist_repos = {k: v for k, v in exist_repos.items() if k in repos}

        if len(exist_repos) >= 1:
            cmds = []
            orders = []
            for _, prop in exist_repos.items():
                cmds.append(cmd)
                orders.append({"cwd": prop["path"]})

            return self.executor.exec_parallel(*cmds, orders=orders, flags=WAITING)

        for _, prop in exist_repos.items():
            self.executor.exec(cmd, flags=WAITING, cwd=prop["path"])
