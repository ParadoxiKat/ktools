# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#Simple setup script. Probably improveable

import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="ktools",
    version="0.1",
    author="Katie Durden",
    author_email="blackmagicgirl@users.noreply.github.com",
    description="A small collection of Katie's favorite miscellaneous utilitiesb",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/blackmagicgirl/ktools.git",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2/3",
        "License :: OSI Approved :: Mozilla Public License 2.0",
        "Operating System :: OS Independent",
    ],
)