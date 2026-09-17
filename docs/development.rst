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

Code style is enforced by pre-commit hooks; see ``.pre-commit-config.yaml``.

Maintainer commands
-------------------

Add NCBI genome to catalog::

    leishref dev fetch --accession GCA_000227135.2

Downloads metadata and FASTA/GFF from NCBI, creates ``leishref/data/ncbi/GCA_000227135.2/metadata.yaml``.

Add local assembly to catalog::

    leishref dev add ~/my_assembly.fasta --technology pacbio

Adds local FASTA to catalog as a new genome entry with metadata.

Scaffold assembly against reference::

    leishref dev scaffold --query query.fasta --reference Ld1S

Creates scaffolded assembly by aligning query to reference, adds to ``leishref/data/scaffold/``.

Publish scaffold to Zenodo::

    leishref dev publish scaffold.fasta

Uploads scaffold files to Zenodo, records DOI in catalog metadata.
