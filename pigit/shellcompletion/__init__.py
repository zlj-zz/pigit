from .bash import BashCompletion
from .zsh import ZshCompletion
from .fish import FishCompletion


supported_shell = {
    "bash": BashCompletion,
    "zsh": ZshCompletion,
    "fish": FishCompletion,
}


def shell_compele(shell: str, prog: str, complete_var: str, script_dir: str):
    # check shell validable.
    shell = shell.lower()

    if not shell:
        print("No shell be found!")
        return

    if shell not in supported_shell:
        print(
            "shell name '{0}' is not supported, see {1}".format(
                shell, supported_shell.keys()
            )
        )
        return

    print("\n===Try to add completion ...")
    print(":: Completion shell: %s" % repr(shell))

    complete_handle = supported_shell[shell](prog, complete_var, script_dir)

    # try create completion file.
    completion_src = complete_handle.generate_resource()
    if not complete_handle.write_completion(completion_src):
        print(":: Write completion script failed.")
        return None

    # try inject to shell config.
    try:
        injected = complete_handle.inject_into_shell()
        if injected:
            print(":: Source your shell configuration.")
        else:
            print(":: Command already exist.")
    except Exception as e:
        print(str(e))
