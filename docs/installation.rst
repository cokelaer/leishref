Installation
=============

From PyPI
---------

The simplest way to install leishref is from PyPI::

    pip install leishref

Verify the installation::

    leishref info

From source
-----------

For development, clone the repository and use Poetry::

    git clone git@github.com:cokelaer/leishref.git
    cd leishref
    poetry install --with dev

Optional dependencies
---------------------

For maintainer commands (``leishref dev``), you need:

- ``ragtag.py`` for scaffolding
