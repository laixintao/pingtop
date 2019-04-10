# -*- coding: utf-8 -*-

from distutils.core import setup
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "readme.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="pingtop",
    version="0.2.6",
    py_modules=["ping"],
    description="Ping multiple servers and show the result in a top like terminal UI.",
    author="laixintao",
    author_email="laixintaoo@gmail.com",
    url="https://github.com/laixintao/pingtop",
    entry_points={"console_scripts": ["pingtop = pingtop:multi_ping"]},
    scripts=["pingtop.py"],
    install_requires=["panwid", "click"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
    ],
    keywords=["IP", "ping", "icmp"],
    long_description=long_description,
    long_description_content_type="text/markdown",
)
