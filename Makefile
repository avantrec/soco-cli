all: setup.py LICENSE README.md requirements.txt soco_cli/*.py
	python setup.py sdist bdist_wheel

clean:
	rm -rf build dist soco_cli.egg.info
