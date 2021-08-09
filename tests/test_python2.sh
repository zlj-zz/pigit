
echo $(pwd)

PY2=$(whereis python2)
echo ${PY2}

Project=tests

${PY2} ${Project}/run.py
Sleep 2
${PY2} ${Project}/run.py -h
Sleep 2
${PY2} ${Project}/run.py -v
Sleep 2
${PY2} ${Project}/run.py -s
Sleep 2
${PY2} ${Project}/run.py -t
Sleep 2
${PY2} ${Project}/run.py -S Branch
Sleep 2
${PY2} ${Project}/run.py -f
Sleep 2
${PY2} ${Project}/run.py -i
Sleep 2
${PY2} ${Project}/run.py ws
Sleep 2
${PY2} ${Project}/run.py wS
Sleep 2
${PY2} ${Project}/run.py --count
Sleep 2
${PY2} ${Project}/run.py --create-ignore python
cat ./.gitignore
git checkout -- .gitignore
