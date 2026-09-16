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

The catalog is counted and then listed by section - NCBI first, then TriTrypDB, then
scaffolds derived here, then anything else::

    Catalog: 161 genomes  (/.../leishref/data)
      NCBI           154
      TriTrypDB        1
      Scaffold         6
      Other            0

    NCBI (154)
      GCA_902369305.1    Leishmania adleri
      ...

    Scaffold (6)
      Ltropica.Ld1S.scaffold.flye    Leishmania tropica - CDC  zenodo

Scaffolds and anything under "Other" are the entries distributed through Zenodo rather
than an archive of their own; those carrying a DOI are marked ``zenodo``. The local
database is listed afterwards with the catalog entry each install came from.

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

Scaffold an assembly against a reference using RagTag. Both query and reference may be
a path to a FASTA file or the name of an installed genome. The result describes the
query (so scaffolding *L. tropica* onto *L. donovani* reference yields *L. tropica*
assembly).

The scaffold is named as ``<query_alias>.scaffold.<ref_alias>`` by default, where
aliases resolve to catalog aliases or identifiers. For TriTrypDB genomes, the suffix
``_tritryp`` is added to avoid collisions with NCBI names. Species codes use single
letters where unambiguous (Ld, Lm, Li) and two letters where ambiguous (Ltr, Lta, Ltu).
Pass ``--alias`` to use a custom name::

    leishref dev scaffold --query LtrL590 --reference Ld1S
    leishref dev scaffold --query genome.fa --reference Ld1S --alias custom.name \
        --species "Leishmania tropica" --strain CDC
    leishref dev scaffold --query LtrL590 --reference Ld1S --alias custom --clean

When the query is a bare FASTA, ``--species`` and ``--strain`` are required; for
catalog genomes these are read from metadata. The ``--clean`` flag keeps only
chromosome-anchored contigs plus kinetoplast.

leishref dev publish
~~~~~~~~~~~~~~~~~~~~

Deposit on Zenodo::

    leishref dev publish FASTA

leishref dev derive-agp
~~~~~~~~~~~~~~~~~~~~~~~

Derive an AGP from two assemblies::

    leishref dev derive-agp --parent PARENT.fa --query QUERY.fa
