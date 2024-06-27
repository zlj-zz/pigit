import enum
from typing import Callable, Dict, List, Tuple, TypedDict, Union


@enum.unique
class GitCommandType(enum.Enum):
    Branch = "Branch"
    Commit = "Commit"
    Conflict = "Conflict"
    Fetch = "Fetch"
    Index = "Index"
    Log = "Log"
    Merge = "Merge"
    Push = "Push"
    Remote = "Remote"
    Stash = "Stash"
    Tag = "Tag"
    WorkingTree = "Working tree"
    Submodule = "Submodule"
    Setting = "Setting"
    Extra = "Extra"  # default


GitCommand = Union[str, Callable[[Union[List, Tuple]], None]]


class GitProxyOptions(TypedDict):
    belong: GitCommandType
    command: GitCommand
    help: str
    has_arguments: bool


GitProxyOptionsGroup = Dict[str, GitProxyOptions]
