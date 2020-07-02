import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sonos-cli",
    version="0.0.1",
    author="Avantrec Ltd",
    author_email="sonos-cli@avantrec.com",
    description="Sonos command line utility, based on SoCo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avantrec/sonos-cli",
    packages=setuptools.find_packages("sonos-cli"),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)