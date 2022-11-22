.PHONY: help prepare-dev test lint lint-check

VENV_NAME?=venv
VENV_ACTIVATE=. $(VENV_NAME)/bin/activate
PYTHON=${VENV_NAME}/bin/python3

.DEFAULT: help
help:
	@echo "make prepare-dev"
	@echo "       prepare development environment, use only once"
	@echo "make test"
	@echo "       run tests"
	@echo "make lint"
	@echo "       run linters"

prepare-dev:
	make venv

venv: $(VENV_NAME)/bin/activate
$(VENV_NAME)/bin/activate: requirements.txt requirements-dev.txt
	test -d $(VENV_NAME) || python3 -m venv $(VENV_NAME)
	${PYTHON} -m pip install -U pip pip-tools
	${PYTHON} -m pip install -r requirements-dev.txt
	touch $(VENV_NAME)/bin/activate

venv-prod: requirements.txt
	test -d $(VENV_NAME) || python3 -m venv $(VENV_NAME)
	${PYTHON} -m pip install -U pip
	${PYTHON} -m pip install -r requirements.txt

test: venv
	$(VENV_ACTIVATE) && ${PYTHON} -m pytest

lint: venv
	$(VENV_ACTIVATE) && ${PYTHON} -m black src/ tests/
	$(VENV_ACTIVATE) && ${PYTHON} -m flake8 src/ tests/ --max-line-length 100 --statistics --show-source


lint-check: venv
	$(VENV_ACTIVATE) && ${PYTHON} -m black --check src/ tests
	$(VENV_ACTIVATE) && ${PYTHON} -m flake8 src/ tests/ --max-line-length 100 --statistics --show-source

requirements: requirements.txt requirements-dev.txt

requirements.txt: pyproject.toml
	$(VENV_ACTIVATE) && ${VENV_NAME}/bin/pip-compile --output-file=requirements.txt pyproject.toml

requirements-dev.txt: pyproject.toml
	$(VENV_ACTIVATE) && ${VENV_NAME}/bin/pip-compile --extra=dev --output-file=requirements-dev.txt pyproject.toml

server: venv
	$(VENV_ACTIVATE) && PYTHONPATH="${PYTHONPATH}:src" ${VENV_NAME}/bin/uvicorn api:app --reload
