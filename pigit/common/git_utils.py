# -*- coding:utf-8 -*-

import os
import re
import logging

from .utils import exec_cmd

Log = logging.getLogger(__name__)


def git_version() -> str:
    """Get Git version."""

    _, git_version_ = exec_cmd("git --version")
    Log.debug("Detect git version:" + str(git_version_))
    return git_version_ or ""


def current_repository() -> tuple[str, str]:
    """
    Get the current git repository path. If not, the path is empty.
    Get the local git config path. If not, the path is empty.

    Return:
        (tuple[str, str]): repository path, git config path.
    """

    err, path = exec_cmd("git rev-parse --git-dir")

    repo_path: str = ""
    git_conf_path: str = ""

    if err:
        return repo_path, git_conf_path

    # remove useless space.
    path = path.strip()

    if ".git/submodule/" in path:
        # this repo is submodule.
        git_conf_path = path
        repo_path = path.replace(".git/submodule/", "")
    if path == ".git":
        repo_path = os.getcwd()
        git_conf_path = os.path.join(repo_path, ".git")
    else:
        git_conf_path = path
        repo_path = path[:-5]

    Log.debug("Final repo: {0}, {1}".format(repo_path, git_conf_path))
    return repo_path, git_conf_path


def parse_git_config(conf: str) -> dict:
    conf = re.split(r"\r\n|\r|\n", conf)
    config_dict: dict[str, dict[str, str]] = {}
    config_type: str = ""

    for line in conf:
        line = line.strip()

        if not line:
            continue

        elif line.startswith("["):
            config_type = line[1:-1].strip()
            config_dict[config_type] = {}

        elif "=" in line:
            key, value = line.split("=", 1)
            config_dict[config_type][key.strip()] = value.strip()

        else:
            continue

    # debug info.
    Log.debug(config_dict)

    return config_dict


if __name__ == "__main__":
    from pprint import pprint

    conf = """
    [core]
        repositoryformatversion = 0
        filemode = true
        bare = false
        logallrefupdates = true
        ignorecase = true
        precomposeunicode = true
    [remote "origin"]
        url = https://github.com/zlj-zz/pigit.git
        fetch = +refs/heads/*:refs/remotes/origin/*
    [branch "main"]
        remote = origin
        merge = refs/heads/main
    [branch "pygittolls"]
        remote = origin
        merge = refs/heads/pygittolls
    [branch "pygittools"]
        remote = origin
        merge = refs/heads/pygittools
    [credential]
        helper = store
    [branch "split_file"]
        remote = origin
        merge = refs/heads/split_file
    [branch "singla_file"]
        remote = origin
        merge = refs/heads/singla_file
    [branch "compat-for-2"]
        remote = origin
        merge = refs/heads/compat-for-2
    """
    pprint(parse_git_config(conf))
