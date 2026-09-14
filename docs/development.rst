Development
============

Contributing
------------

The repository structure::

    leishref/
      __init__.py
      cli.py           # Command-line interface
      metadata.py      # Genome metadata handling
      ncbi.py          # NCBI datasets integration
      agp.py           # AGP parsing and manipulation
      scaffold.py      # Ragtag scaffolding wrapper
      zenodo.py        # Zenodo publishing
      data/            # Shipped catalog (metadata.yaml per genome)

Testing
-------

Run the test suite::

    poetry install --with dev
    pytest

With coverage::

    pytest --cov=leishref --cov-report=term-missing

Linting
-------

Code style checks::

    black --check leishref tests
    isort --check-only leishref tests
    flake8 leishref tests

Auto-format::

    black leishref tests
    isort leishref tests

Maintainer commands
-------------------

Fetch genomes from NCBI::

    leishref dev fetch --accession GCA_000227135.2

Add local assemblies::

    leishref dev add ~/my_assembly.fasta --technology pacbio

Scaffold against a reference::

    leishref dev scaffold --query query.fasta --reference Ld1S

Publish to Zenodo::

    leishref dev publish scaffold.fasta
