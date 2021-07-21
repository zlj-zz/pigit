Project = pygittools
PY ?= $(shell (python3 -c 'import sys; sys.exit(sys.version < "3.6")' && \
	      which python3) )

ifeq ($(PY),)
  $(error No suitable python found(>=3.7).)
endif

run:
	$(PY) ./tests/test_run.py

lint:
	@if [ ! -f flake8 ]; then $(PY) -m pip install flake8; fi
	@flake8 -v --ignore=E501,E402,E203,E741 --show-source
	@echo

clean:
	find . -type f -name *.pyc -delete
	find . -type d -name __pycache__ -delete

del: clean
	@if [ -d ./dist ]; then rm -r ./dist/; fi
	@if [ -d ./build ]; then rm -r ./build; fi
	@if [ -d ./$(Project).egg-info ]; then rm -r "./$(Project).egg-info"; fi

release: del
	$(PY) setup.py sdist bdist_wheel
	twine upload dist/*

install: del
	$(PY) setup.py install

todo:
	@grep --color -Ion '\(TODO\|XXX\).*' -r fungit

.PHONY: run lint clean del install release todo
