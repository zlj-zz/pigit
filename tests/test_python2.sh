
echo $(pwd)

PY2=$(whereis python2)
echo ${PY2}

Project=pygittools

${PY2} ${Project}/__init__.py
Sleep 2
${PY2} ${Project}/__init__.py -s
Sleep 2
${PY2} ${Project}/__init__.py -t
Sleep 2
${PY2} ${Project}/__init__.py -S Branch
Sleep 2
${PY2} ${Project}/__init__.py -h
Sleep 2
${PY2} ${Project}/__init__.py -f
Sleep 2
${PY2} ${Project}/__init__.py -i
Sleep 2
${PY2} ${Project}/__init__.py -v
Sleep 2
${PY2} ${Project}/__init__.py ws
Sleep 2
${PY2} ${Project}/__init__.py wS
Sleep 2
${PY2} ${Project}/__init__.py --count
