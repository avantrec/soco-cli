SRC = setup.py soco_cli/*.py
ASSETS = LICENSE README.md MANIFEST.in requirements.txt
BUILD_DIST = build dist soco_cli.egg-info
PYCACHE = soco_cli/__pycache__ __pycache__

build: $(SRC) $(ASSETS)
	python setup.py sdist bdist_wheel

clean:
	rm -rf $(BUILD_DIST) $(PYCACHE)

install: build
	pip install -U -e .

uninstall:
	pip uninstall -y soco_cli

black: setup.py soco_cli/*.py
	black setup.py soco_cli/*.py

pypi_upload: clean build
	python -m twine upload --repository pypi dist/*
