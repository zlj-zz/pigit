Project = pigit
PY ?= $(shell (python3 -c 'import sys; sys.exit(sys.version_info < (3, 7))' && which python3) )

ifeq ($(PY),)
  $(error No suitable python found(>=3.8).)
endif

run:
	$(PY) ./tools/run.py

test:
	@if [ ! -f pytest ]; then $(PY) -m pip install pytest; fi
	pytest ./tests
	# pytest ./tests --cov=pigit --cov-report=html

lint:
	@if [ ! -f flake8 ]; then $(PY) -m pip install flake8; fi
	@flake8 -v --ignore=W503,F403,F405,E501,E402,E203,E741,E401 --show-source ./pigit
	@echo

clear:
	# clear code cache
	@find . -type f -name *.pyc -delete
	@find . -type d -name __pycache__ -delete

del: clear
	# del build generate
	@if [ -d ./dist ]; then rm -r ./dist/; fi
	@if [ -d ./build ]; then rm -r ./build; fi
	@if [ -d ./$(Project).egg-info ]; then rm -r "./$(Project).egg-info"; fi

	# del test cache
	@find . -type d -name .pytest_cache -delete

	# del cov file
	@if [ -d ./htmlcov ]; then rm -r ./htmlcov; fi
	@find . -type f -name *.coverage* -delete

release: del
	$(PY) setup.py sdist bdist_wheel
	twine upload dist/*

install: del
	$(PY) -m pip uninstall pigit
	$(PY) setup.py install

todo:
	@grep --color -Ion '\(TODO\|XXX\|FIXME\).*' -r $(Project)

uml:
	pyreverse -ASmy -o png pigit -d docs

.PHONY: run lint clear del install release todo test uml
