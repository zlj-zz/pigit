import os

def print_user(args):
    print(os.system('whoami'))

extra_cmds = {
    'gconf': {
        'command': 'git config --global --edit',
		'help': 'Edit your configuration file in your editor.'
    },
    'fix-author': {
        'command': 'git commit --amend --reset-author',
		'help': 'You may fix the identity used for this commit.'
    },
    'print-user': {
        'command': print_user,
        'type': 'func',
        'help': 'print system user name.'
    }
}
