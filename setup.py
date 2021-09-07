import sys

PYTHON_VERSION = sys.version_info[:2]
if PYTHON_VERSION < (3, 6):
    print(
        "The current version of pigit does not support less "
        "than Python3.6, please install 1.0.9"
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
import pigit

setup(
    name=pigit.__project__,
    version=pigit.__version__,
    author=pigit.__author__,
    author_email=pigit.__email__,
    description="Simple terminal tool of Git.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=pigit.__url__,
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Shells",
        "Topic :: Software Development",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
    ],
    install_requires=[],
    entry_points="""
        [console_scripts]
        pigit=pigit:main
    """,
    python_requires=">=3.6",
)
