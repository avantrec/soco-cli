import io
import re

import setuptools

with open("PYPI_README.md", "r") as fh:
    long_description = fh.read()

src = io.open("soco_cli/__init__.py", encoding="utf-8").read()
metadata = dict(re.findall('__([a-z]+)__ = "([^"]+)"', src))
# docstrings = re.findall('"""(.*?)"""', src, re.MULTILINE | re.DOTALL)

REQUIREMENTS = list(open("requirements.txt"))
VERSION = metadata["version"]

setuptools.setup(
    name="soco-cli",
    version=VERSION,
    author="Avantrec Ltd",
    author_email="soco_cli@avantrec.com",
    description="Sonos command line control utility, based on SoCo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avantrec/soco-cli",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
    python_requires=">=3.5",
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "sonos=soco_cli.sonos:main",
            "soco=soco_cli.sonos:main",
            "sonos-discover=soco_cli.sonos_discover:main",
            "soco-discover=soco_cli.sonos_discover:main",
            "sonos-http-api-server=soco_cli.http_api:main",
            "soco-http-api-server=soco_cli.http_api:main",
        ]
    },
)
