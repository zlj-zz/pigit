# https://github.com/github/gitignore
# Crawling `.gitignore` template file from github.

import os
import urllib3
from typing import Dict, List

urllib3.disable_warnings()

import requests


_target_url = "https://github.com/github/gitignore/blob/main/{}.gitignore"


_val_template = '''
_{0}: str = r"""
{1}
"""
'''

_code_template = """
# https://github.com/github/gitignore
# Generate by script `gitignore.py`.

from typing import Dict


%(vals)s


IGNORE_TEMPLATE: Dict[str, str] = {
%(kvs)s
}

__all__ = ("IGNORE_TEMPLATE",)
"""


def standardized_val_name(name: str) -> str:
    return name.replace("-", "_")


def _get(url: str) -> str:
    resp = requests.get(url, verify=False)

    if resp.status_code == 200:
        # print("content:", resp.content)
        # print("json:", resp.json())
        rawlines = resp.json()["payload"]["blob"]["rawLines"]
        return "\n".join(rawlines)
    else:
        return ""


def _generate_val(v: str, t: str) -> str:
    content = _get(_target_url.format(t))
    code = _val_template.format(standardized_val_name(v), content).strip()

    return code


def _generate_code(targets: Dict) -> str:
    vals: List[str] = []
    kvs: List[str] = []

    for v, t in targets.items():
        vals.append(_generate_val(v, t))
        kvs.append(f'    "{v}": _{standardized_val_name(v)},')
        print(f"{t} ", end="", flush=True)
    print("")

    code = _code_template % {"vals": "\n\n\n".join(vals), "kvs": "\n".join(kvs)}
    return code


ignore_targets = {
    "android": "Android",
    "cpp": "C++",
    "c": "C",
    "cmake": "CMake",
    "cuda": "CUDA",
    "d": "D",
    "dart": "Dart",
    "elisp": "Elisp",
    "erlang": "Erlang",
    "gitbook": "GitBook",
    "go": "Go",
    "java": "Java",
    "julia": "Julia",
    "kotlin": "Java",
    "lua": "Lua",
    "maven": "Maven",
    "node": "Node",
    "objective-c": "Objective-C",
    "perl": "Perl",
    "python": "Python",
    "qt": "Qt",
    "r": "R",
    "ros": "ROS",
    "ruby": "Ruby",
    "rust": "Rust",
    "sass": "Sass",
    "scala": "Scala",
    "swift": "Swift",
    "tex": "TeX",
    "unity": "Unity",
    "visualstudio": "VisualStudio",
}

if __name__ == "__main__":
    code = _generate_code(ignore_targets)

    project_path = os.path.dirname(os.path.dirname(__file__))
    with open(f"{project_path}/pigit/git/ignore/template.py", "w+") as f:
        f.write(code)
