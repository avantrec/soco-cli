import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

REQUIREMENTS = list(open("requirements.txt"))

setuptools.setup(
    name="soco-cli",
    version="0.0.1",
    author="Avantrec Ltd",
    author_email="soco_cli@avantrec.com",
    description="Sonos command line utility, based on SoCo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avantrec/soco-cli",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.5",
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "sonos=soco_cli.sonos:main",
            "sonos-discover=soco_cli.sonos_discover:main",
        ]
    },
)
