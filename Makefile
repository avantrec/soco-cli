build: LICENSE README.md MANIFEST.in requirements.txt setup.py soco_cli/*.py
	python setup.py sdist bdist_wheel

clean:
	rm -rf build dist soco_cli.egg.info __pycache__ soco_cli/__pycache__

install: build
	pip install -U -e .

uninstall:
	pip uninstall -y soco_cli

black: setup.py soco_cli/*.py
	black setup.py soco_cli/*.py
