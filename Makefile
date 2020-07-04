.DEFAULT_GOAL := no_op

SRC = setup.py soco_cli/*.py
MANIFEST = LICENSE README.md MANIFEST.in requirements.txt
BUILD_DIST = build dist soco_cli.egg-info
PYCACHE = soco_cli/__pycache__ __pycache__

build: $(SRC) $(MANIFEST)
	python setup.py sdist bdist_wheel

clean:
	rm -rf $(BUILD_DIST) $(PYCACHE)

install: build
	pip install -U -e .

uninstall:
	pip uninstall -y soco_cli

black: $(SRC)
	black setup.py soco_cli/*.py

pypi_upload: clean build
	python -m twine upload --repository pypi dist/*

pypi_check: build
	twine check dist/*

no_op:
	# Available targets are: build, clean, install, uninstall, black, pypi_upload, pypi_check
