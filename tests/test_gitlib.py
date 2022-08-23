import os, sys, pytest
from unittest.mock import patch, Mock

from .conftest import TEST_PATH
from pigit.common.utils import exec_cmd
from pigit.gitlib.options import GitOption
from pigit.gitlib.processor import ShortGitter, get_extra_cmds
from pigit.gitlib._cmd_func import add, set_email_and_username, fetch_remote_branch
from pigit.gitlib.ignore import get_ignore_source, create_gitignore, IGNORE_TEMPLATE


class TestGitOption:
    git = GitOption()
    if not git.git_version:
        exit(1)

    # =================
    # create test repo
    # =================
    test_repo = os.path.join(TEST_PATH, "test_repo")
    os.makedirs(test_repo, exist_ok=True)
    print(exec_cmd("git init", cwd=test_repo))
    with open(os.path.join(test_repo, "test1.txt"), "w") as f:
        f.write("""This is a test file.""")
    print(exec_cmd("git add .", cwd=test_repo))
    print(exec_cmd("git commit -m 'init'", cwd=test_repo))
    with open(os.path.join(test_repo, "test2.py"), "w") as f:
        f.write("""print('This is test py file.')""")

    git.update_setting(
        op_path=test_repo, repo_info_path=os.path.join(test_repo, "reps.json")
    )

    def test(self):
        git = self.git
        print()

        print(git.get_head())
        print(git.get_branches())
        print(git.get_first_pushed_commit())
        print(git.get_remotes())
        print(git.get_remote_url())
        print(git.get_repo_desc())

    def test1(self):
        git = self.git
        print(git.load_branches())
        print(git.load_log())
        print(git.load_status())
        print(git.load_file_diff("example.py", tracked=False))
        print(git.load_commits("main"))
        print(git.load_commit_info(git.get_first_pushed_commit()))

    @pytest.mark.parametrize(
        ["get_path", "expected"],
        [
            [("err", ""), ("", "")],
            [("", "a/b/.git"), ("a/b", "a/b/.git")],
            [("", "a/b/.git/modules/"), ("a/b/", "a/b/.git/modules/")],
        ],
    )
    @patch("pigit.gitlib.options.exec_cmd")
    def test_get_repo_info(self, mock_exec_cmd, get_path, expected):
        mock_exec_cmd.return_value = get_path
        assert self.git.get_repo_info() == expected

    def test_get_repo_info_2(self):
        git = self.git
        test_repo = self.test_repo
        assert git.get_repo_info() == (test_repo, os.path.join(test_repo, ".git"))
        assert git.get_repo_info("xxxxxxx") == ("", "")

    # def pytest_sessionfinish(session, exitstatus):
    #     """whole test run finishes."""
    #     print("finish")
    #     os.rmdir(test_repo)


class TestShortGitter:
    def test_init_error(self):
        with pytest.raises(TypeError):
            ShortGitter(extra_cmds="xxx")

    @pytest.fixture(scope="module")
    def setup(self):
        extra = {"aa": {"help": "print system user name."}}
        return ShortGitter(extra_cmds=extra)

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git add xxx/xxx",
            "git checkout -b test",
            "git log --online --graph",
            "git log --dep 10 --online --graph",
            "git log --dep 10 --online --graph --color true",
            'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit"',
        ],
    )
    def test_color_command(self, setup, command: str):
        from plenty import get_console

        console = get_console()
        handle = setup

        color_str = handle.color_command(command)
        console.echo(color_str)

    def test_load_extra_cmds(self):
        """Test load extra custom cmds."""

        name = "test_module"
        file = f"./{name}.py"
        with open(file, "w") as f:
            f.write("""extra_cmds = { 'A': 1 }""")

        d = get_extra_cmds(name, file)
        assert d["A"] == 1

        os.remove(file)


class TestCmdFunc:
    @patch("pigit.gitlib._cmd_func.exec_cmd", return_value=None)
    def test_add(self, _):
        add([])

    @patch("pigit.gitlib._cmd_func.exec_cmd", return_value=None)
    def test_fetch_remote(self, _):
        fetch_remote_branch([])

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("--global",),
            ("global",),
            ("-g",),
        ],
    )
    @patch("builtins.input", return_value="abc@gmail.com")
    @patch("pigit.gitlib._cmd_func.exec_cmd", return_value=False)
    def test_set_ua(self, _a, _b, args):
        set_email_and_username(args)


def test_iter_ignore():
    for t in IGNORE_TEMPLATE:
        print(get_ignore_source(t))


@pytest.mark.parametrize(
    ["type_", "file_name", "dir_path", "writting"],
    [
        ["xxxxxx", "ignore_text", TEST_PATH, False],
        ["rust", "ignore_test", TEST_PATH, False],
        ["rust", "ignore_test", TEST_PATH, True],
    ],
)
def test_ignore(type_, file_name, dir_path, writting):
    code, msg = create_gitignore(
        type_, file_name=file_name, dir_path=dir_path, writting=writting
    )
    print(code, msg)
