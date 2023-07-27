.DEFAULT_GOAL := no_op

SRC = setup.py soco_cli/*.py
TESTS = tests/*.py
MANIFEST = LICENSE README.md PYPI_README.md MANIFEST.in requirements.txt
BUILD_DIST = build dist soco_cli.egg-info
PYCACHE = soco_cli/__pycache__ tests/__pycache__ __pycache__
TOC = README.md.*

build: $(SRC) $(MANIFEST)
	python -m build

clean:
	rm -rf $(BUILD_DIST) $(PYCACHE) $(TOC)

install: build
	pip install -U -e .

uninstall:
	pip uninstall -y soco_cli

black: $(SRC)
	black --preview $(SRC) $(TESTS)

isort: $(SRC)
	isort --profile black $(SRC) $(TESTS)

format: isort black

mypy: $(SRC) $(TESTS)
	mypy $(SRC) $(TESTS)

pypi_upload: clean build
	python -m twine upload --repository pypi dist/*

pypi_test: clean build
	python -m twine upload --repository testpypi dist/*

pypi_check: build
	twine check dist/*

toc:
	./gh-md-toc --insert README.md

update:
	pip install -U -r requirements.txt -r requirements-dev.txt

no_op:
	# Available targets are: build, clean, install, uninstall, black, pypi_upload, pypi_check
