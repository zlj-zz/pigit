#!/usr/bin/env sh
# run scirpit with `source`.
#
# Usage:
#    create: `source <scirpt>`
#    activate: `source <scirpt> start`
#    deactivate: `source <scirpt> stop`


# Check py version.
version=$(python3 -c 'import sys; sys.exit(sys.version_info < (3, 7))')
echo $version
if [[ "$version" ]]; then
    echo "Python version should be 3.8 or more higher."
    exit 1
fi

op=$1
name=".pigit_venv"

create_venv() {
    if [ -d "$name" ]; then
        echo "Virtual env'$name' existed."
        exit 1
    fi

    python3 -m venv "$name"

    source "$name/bin/activate"

    pip install -r requirements.txt

    echo "Virtual env has created. activate with running:："
    echo "source $name/bin/activate"
}

activate_venv() {
    if [ ! -d "$name" ]; then
        echo "Not found env '$name'."
        exit 1
    fi

    source "$name/bin/activate"
    echo "The virtual env has actived."
}

deactivate_venv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Current not activate virtula env."
        exit 1
    fi

    # exit command
    deactivate
    echo "The virtual env exited."
}


if [[ "$op" == "start" ]]; then
    activate_venv
elif [[ "$op" == "stop" ]]; then
    deactivate_venv
else
    create_venv
fi

