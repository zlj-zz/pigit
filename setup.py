import sys

PYTHON_VERSION = sys.version_info[:3]
if PYTHON_VERSION < (3, 8, 5):
    print(
        "The current version of pigit does not support less "
        "than Python3.8, more version please check https://pypi.org/project/pigit/"
    )
    exit(0)

try:
    LONG_DESCRIPTION = open("README.md", encoding="utf-8").read()
except Exception:
    LONG_DESCRIPTION = """# pigit

A terminal tool for git. When we use git, do you feel very uncomfortable with too long commands.
For example: `git status --short`, this project can help you improve it. This project is written in Python.
Now most UNIX like systems come with Python. So you can easily install and use it.

## Installation

### Pip

```bash
pip install -U pigit
```

### Source

```bash
git clone https://github.com/zlj-zz/pigit.git
cd pigit
make install
# or
python setup.py install  # On windows
```
    """

from setuptools import setup, find_packages
from pigit.const import __project__, __version__, __author__, __email__, __url__

setup(
    name=__project__,
    version=__version__,
    author=__author__,
    author_email=__email__,
    description="Simple terminal tool of Git.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=__url__,
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: System :: Shells",
        "Topic :: Software Development",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
    ],
    install_requires=['plenty==1.0.2'],
    entry_points="""
        [console_scripts]
        pigit=pigit.entry:main
    """,
    python_requires=">=3.8",
)
