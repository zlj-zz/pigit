import pytest

from pigit.git.ignore import get_ignore_source, create_gitignore, IGNORE_TEMPLATE

from .conftest import TEST_PATH


def test_iter_ignore():
    for t in IGNORE_TEMPLATE:
        src = get_ignore_source(t)
        assert type(src) == str
        # print(src)


@pytest.mark.parametrize(
    ["t", "file", "dir", "writing", "expected_code"],
    [
        ["xxxxxx", "ignore_text", TEST_PATH, False, 2],
        ["rust", "ignore_test", TEST_PATH, False, 1],
        ["rust", "ignore_test", TEST_PATH, True, 0],
    ],
)
def test_create_ignore(t, file, dir, writing, expected_code):
    code, msg = create_gitignore(t, file_name=file, dir_path=dir, writing=writing)
    assert code == expected_code
    # print("\n", msg)
