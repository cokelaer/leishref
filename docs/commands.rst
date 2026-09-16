Command Reference
==================

User commands
-------------

leishref download
~~~~~~~~~~~~~~~~~

Install a genome from the catalog::

    leishref download --alias ALIAS ACCESSION
    leishref download GCA_002243465.1 --alias Ld1S

Options:
- ``--alias ALIAS`` — Local directory name (required)
- ``--no-link`` — Don't create symlinks

leishref download-ncbi
~~~~~~~~~~~~~~~~~~~~~~

Download all NCBI genomes from the catalog::

    leishref download-ncbi
    leishref download-ncbi --force
    leishref download-ncbi --verbose

Uses accession as local alias for each genome. Quiet by default (progress bar only).
Reports failed downloads without stopping the batch.

Options:
- ``--force`` — Download again even if already installed
- ``--no-link`` — Skip alias-named symlinks
- ``--verbose`` — Show each download details (MD5, etc) instead of progress bar

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

leishref rename-sequences
~~~~~~~~~~~~~~~~~~~~~~~~~

Rename sequences in an installed genome using chromosome database::

    leishref rename-sequences Ld1S
    leishref rename-sequences Ld1S --flavor number
    leishref rename-sequences Ld1S --flavor roman

Flavors:
- ``chr`` — Rename to 'chromosome I', 'chromosome II', etc.
- ``number`` (default) — Rename to '1', '2', '3', etc. (numeric index)
- ``roman`` — Rename to 'I', 'II', 'III', etc. (Roman numerals)
- ``name`` — Use names from local chromosome database

Requires chromosome info in local database (populated during ``leishref dev fetch`` from NCBI).
Rewrites FASTA file in-place and updates stored checksum.

leishref prune-scaffold
~~~~~~~~~~~~~~~~~~~~~~~

Remove unmapped contigs, keeping only chromosome sequences and kinetoplast::

    leishref prune-scaffold Ld1S

Removes sequences not found in chromosome database while automatically preserving
kinetoplast sequences (recognized by patterns: kinetoplast, maxicircle, maxi,
mitochondrion, etc.). Rewrites FASTA in-place and updates statistics.

Requires chromosome info in local database (populated during ``leishref dev fetch``).

Developer and maintainer commands
----------------------------------

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

Scaffold an assembly against a reference using RagTag. Both query and reference must be
installed catalog genomes. The result describes the query: scaffolding *L. tropica*
onto *L. donovani* reference yields *L. tropica* assembly, with provenance recorded
for the reference. Species and strain are inherited from the query metadata.

The scaffold is named as ``<query_alias>.scaffold.<ref_alias>`` by default, where
aliases resolve to catalog aliases or identifiers. For TriTrypDB genomes, the suffix
``_tritryp`` is added to avoid collisions with NCBI names. Species codes use single
letters where unambiguous (Ld, Lm, Li) and two letters where ambiguous (Ltr, Lta, Ltu).
Pass ``--alias`` to use a custom name. The ``--clean`` flag keeps only
chromosome-anchored contigs plus kinetoplast::

    leishref dev scaffold --query LtrL590 --reference Ld1S
    leishref dev scaffold --query LtrL590 --reference Ld1S --alias custom.name
    leishref dev scaffold --query LtrL590 --reference Ld1S --clean

leishref dev publish
~~~~~~~~~~~~~~~~~~~~

Deposit an installed genome on Zenodo and record the DOI in the catalog. Requires
``ZENODO_TOKEN`` (or ``ZENODO_SANDBOX_TOKEN`` with ``--sandbox``).

The command uploads all associated files: FASTA plus optional AGP (for scaffolds),
and records the DOI so the genome appears in the catalog as ``Zenodo`` source::

    leishref dev publish LtrL590.scaffold.Ld1S
    leishref dev publish LtrL590.scaffold.Ld1S --confirm --version v1.0
    leishref dev publish LtrL590.scaffold.Ld1S --sandbox  # test run

Options:
- ``--confirm`` — Actually publish; without it, shows what would be uploaded (dry-run)
- ``--version`` — Version tag (default ``v1.0``)
- ``--sandbox`` — Publish to sandbox.zenodo.org for testing

For scaffolds, both the FASTA and AGP files are uploaded. The ``--alias`` from
``leishref download`` is used to locate the genome in the local database.

leishref dev remove
~~~~~~~~~~~~~~~~~~~

Remove a genome entry from the catalog::

    leishref dev remove LtrL590.scaffold.Ld1S
    leishref dev remove GCA_000227135.2 --force

Deletes the entire entry directory. Asks for confirmation unless ``--force`` is used.
Useful for removing invalid, duplicate, or superceded entries.

Options:
- ``--force`` — Skip confirmation prompt
- ``--catalog-dir`` — Remove from alternate catalog location

leishref dev derive-agp
~~~~~~~~~~~~~~~~~~~~~~~

Derive an AGP from two assemblies::

    leishref dev derive-agp --parent PARENT.fa --query QUERY.fa
