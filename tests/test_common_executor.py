# -*- coding:utf-8 -*-

from pprint import pprint
import pytest
import time
import textwrap
from unittest.mock import patch

from pigit.common.executor import (
    ENCODING,
    REDIRECT,
    REPLY,
    SILENT,
    WAIT_ENTER,
    WAITING,
    Executor,
)


class TestExecutor:
    @classmethod
    def setup_class(cls):
        cls.executor = Executor(print)

    def test_exec(self):
        print()

        print(self.executor.exec("pwd", flags=WAITING | REDIRECT))

        print(self.executor.exec("pwd", flags=REPLY))
        print(self.executor.exec("pwd", flags=REPLY | ENCODING))
        # # print(self.executor.exec("pwd", flags=REPLY | ENCODING | WAIT_ENTER))

        print(self.executor.exec("xxxxxxxx", flags=REPLY))

        assert self.executor.exec(["ls"], shell=True) == (None, None, None)
        assert self.executor.exec("ls", flags=REPLY | SILENT) == (0, None, None)
        assert self.executor.exec(["which", "python3"], flags=SILENT, shell=True) == (
            None,
            None,
            None,
        )

    def test_exec_async(self):
        code = textwrap.dedent(
            """\
            # -*- coding:utf-8 -*-

            if __name__ == '__main__':
                import time

                print({0})
                time.sleep(int({0}))
                print({0})
            """
        )

        cmds = [["python3", "-c", code.format(i)] for i in range(5, 0, -1)]
        # pprint(cmds)

        start_t = time.time()
        results = self.executor.exec_async(*cmds, flags=WAITING | REDIRECT)
        assert results == [(None, None, None)] * 5
        # results = self.executor.exec_async(*cmds, flags=REPLY)
        # results = self.executor.exec_async(*cmds, flags=REPLY | SILENT)
        end_t = time.time()

        print(end_t - start_t)
        assert end_t - start_t < 6

        pprint(results)
