"""Backward-compatible entry for ``python setup.py install`` / ``sdist``.

Project metadata and dependencies live in ``pyproject.toml`` (PEP 517/518).
"""

import sys

if sys.version_info < (3, 8, 5):
    print(
        "The current version of pigit does not support less "
        "than Python 3.8.5; see https://pypi.org/project/pigit/"
    )
    sys.exit(1)

from setuptools import setup

if __name__ == "__main__":
    setup()
