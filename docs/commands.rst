Command Reference
==================

User commands
-------------

leishref download
~~~~~~~~~~~~~~~~~

Install a genome from the catalog::

    leishref download --alias ALIAS ACCESSION

Options:
- ``--alias ALIAS`` — Local directory name
- ``--no-link`` — Don't create symlinks

leishref info
~~~~~~~~~~~~~

List catalog and local genomes::

    leishref info

Shows species, strain, accession, and local installation status.

leishref search
~~~~~~~~~~~~~~~

Search the catalog::

    leishref search TERM [TERM ...]

Returns all genomes matching all terms.

leishref verify
~~~~~~~~~~~~~~~

Check integrity of local genomes::

    leishref verify

Verifies MD5 checksums.

leishref link
~~~~~~~~~~~~~

Refresh symlinks to local genomes::

    leishref link

Developer commands
------------------

All maintainer commands are under ``leishref dev``::

    leishref dev --help

leishref dev fetch
~~~~~~~~~~~~~~~~~~~

Add a genome from NCBI::

    leishref dev fetch --accession GCA_000227135.2

leishref dev add
~~~~~~~~~~~~~~~~

Add a local assembly::

    leishref dev add FASTA [--technology TECH]

leishref dev scaffold
~~~~~~~~~~~~~~~~~~~~~

Scaffold an assembly::

    leishref dev scaffold --query QUERY.fa --reference REF_ALIAS

leishref dev publish
~~~~~~~~~~~~~~~~~~~~

Deposit on Zenodo::

    leishref dev publish FASTA

leishref dev derive-agp
~~~~~~~~~~~~~~~~~~~~~~~

Derive an AGP from two assemblies::

    leishref dev derive-agp --parent PARENT.fa --query QUERY.fa
