# https://github.com/github/gitignore
# Crawling `.gitignore` template file from github.

import os
from typing import Dict, List

import requests

_RAW_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/github/gitignore/main/{}.gitignore"
)

_val_template = '''
_{0}: str = r"""
{1}
"""
'''

_code_template = """# -*- coding:utf-8 -*-
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


def _get(template_github_name: str) -> str:
    """Fetch raw .gitignore text from github/gitignore (main branch)."""
    url = _RAW_URL_TEMPLATE.format(template_github_name)
    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException:
        return ""
    if resp.status_code != 200:
        return ""
    return resp.text


def _generate_val(v: str, t: str) -> str:
    content = _get(t)
    return _val_template.format(standardized_val_name(v), content).strip()


def _generate_code(targets: Dict[str, str]) -> str:
    vals: List[str] = []
    kvs: List[str] = []

    for v, t in targets.items():
        vals.append(_generate_val(v, t))
        kvs.append(f'    "{v}": _{standardized_val_name(v)},')
        print(f"{t} ", end="", flush=True)
    print("")

    payload = {"vals": "\n\n\n".join(vals), "kvs": "\n".join(kvs)}
    return _code_template % payload


ignore_targets = {
    "ada": "Ada",
    "android": "Android",
    "angular": "Angular",
    "cpp": "C++",
    "c": "C",
    "cmake": "CMake",
    "cuda": "CUDA",
    "d": "D",
    "dart": "Dart",
    "delphi": "Delphi",
    "eagle": "Eagle",
    "elisp": "Elisp",
    "erlang": "Erlang",
    "flutter": "Flutter",
    "githubpages": "GitHubPages",
    "gitbook": "GitBook",
    "go": "Go",
    "java": "Java",
    "julia": "Julia",
    "katalon": "Katalon",
    "kotlin": "Kotlin",
    "lua": "Lua",
    "maven": "Maven",
    "nestjs": "Nestjs",
    "nextjs": "Nextjs",
    "node": "Node",
    "objective-c": "Objective-C",
    "perl": "Perl",
    "python": "Python",
    "qooxdoo": "Qooxdoo",
    "qt": "Qt",
    "r": "R",
    "ros": "ROS",
    "ruby": "Ruby",
    "rust": "Rust",
    "sass": "Sass",
    "scala": "Scala",
    "scheme": "Scheme",
    "swift": "Swift",
    "tex": "TeX",
    "unity": "Unity",
    "vba": "VBA",
    "visualstudio": "VisualStudio",
    "waf": "Waf",
}

if __name__ == "__main__":
    code = _generate_code(ignore_targets)

    project_path = os.path.dirname(os.path.dirname(__file__))
    out_path = f"{project_path}/pigit/git/ignore/template.py"
    with open(out_path, "w+", encoding="utf-8") as f:
        f.write(code)
