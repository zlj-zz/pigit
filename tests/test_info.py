from .utils import analyze_it

from pigit import Parser, introduce
from pigit.gitinfo import output_repository_info, output_git_local_config


@analyze_it
def test_info():
    introduce()

    output_repository_info()

    output_git_local_config("xxx")
    output_git_local_config("normal")
    output_git_local_config("table")


def test_show_help():
    p = Parser()
    p.parse([""])
    p._parser.print_help()
