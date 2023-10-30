import pytest
from unittest.mock import Mock, patch
from pigit.shellmode import PigitShell


# Test for PigitShell.__init__
def test_shell_init():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}

    # Act
    shell = PigitShell(short_giter)

    # Assert
    assert hasattr(shell, "do_test")


# Test for PigitShell.make_fun
def test_make_fun():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    short_giter.process_command.return_value = (0, "test message")
    shell = PigitShell(short_giter)

    # Act
    func = shell.make_fun("test", "test help")
    func("test args")

    # Assert
    short_giter.process_command.assert_called_once_with("test", ["test", "args"])


# Test for PigitShell.set_instance_method
def test_set_instance_method():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    shell = PigitShell(short_giter)
    func = lambda x: x

    # Act
    shell.set_instance_method(func, "test_func")

    # Assert
    assert hasattr(shell, "test_func")


# Test for PigitShell.default
def test_default():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    shell = PigitShell(short_giter)
    shell.stdout = Mock()

    # Act
    shell.default("test")

    # Assert
    shell.stdout.write.assert_called_once()


# Test for PigitShell.do_help
def test_do_help():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    shell = PigitShell(short_giter)
    shell.stdout = Mock()

    # Act
    shell.do_help("test")

    # Assert
    # do_help will be called twice.
    shell.stdout.write.assert_called()


# Test for PigitShell.do_shell
@patch("os.system")
def test_do_shell(mock_system):
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    shell = PigitShell(short_giter)

    # Act
    shell.do_shell("ls")

    # Assert
    mock_system.assert_called_once_with("ls")


# Test for PigitShell.do_all
def test_do_all():
    # Arrange
    short_giter = Mock()
    short_giter.cmds = {"test": {"help": "test help"}}
    short_giter.get_help.return_value = "test help"
    shell = PigitShell(short_giter)

    # Act
    shell.do_all("")

    # Assert
    short_giter.get_help.assert_called_once()
