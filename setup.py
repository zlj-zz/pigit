import sys

PYTHON_VERSION = sys.version_info[:2]

try:
    LONG_DESCRIPTION = open("README.md").read()
except Exception:
    LONG_DESCRIPTION = ""

from setuptools import setup, find_packages
import pygittools

setup(
    name="pygittools",
    version=pygittools.__version__,
    author=pygittools.__author__,
    author_email=pygittools.__email__,
    description="Simple terminal tool of Git.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=pygittools.__git_url__,
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[],
    entry_points="""
        [console_scripts]
        g=pygittools:command_g
    """,
    # python_requires=">=3.7",
)
