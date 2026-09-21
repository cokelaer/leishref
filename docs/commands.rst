Command Reference
==================

Using the database
------------------

leishref install
~~~~~~~~~~~~~~~~~

Install a genome from the catalog::

    leishref install GCA_002243465.1 --alias Ld1S

Re-running the exact same command is a safe no-op: it just makes sure the
alias-named symlink is in place, without re-downloading or printing anything about
``--force``. ``--force`` is only needed to force a fresh download, or when ALIAS is
already used by a *different* genome - reusing an alias for a different genome
without ``--force`` is refused with a clear error rather than silently swapped.

Options:
- ``--alias ALIAS`` — Local directory name (required)
- ``--force`` — Re-download, or replace a different genome under this alias
- ``--no-link`` — Don't create symlinks

leishref install-ncbi
~~~~~~~~~~~~~~~~~~~~~

Install all NCBI genomes from the catalog::

    leishref install-ncbi
    leishref install-ncbi --force
    leishref install-ncbi --verbose
    leishref install-ncbi --parallel 8

Uses accession as local alias for each genome. Quiet by default (progress bar only).
Reports failed installs without stopping the batch. ``--parallel N`` downloads N
genomes concurrently instead of one at a time (network fetch runs in a thread pool;
the local install step stays sequential so output and ``accessions.txt`` writes
don't race).

Options:
- ``--force`` — Install again even if already installed
- ``--no-link`` — Skip alias-named symlinks
- ``--verbose`` — Show each install details (MD5, etc) instead of progress bar
- ``--parallel N`` — Download N genomes concurrently (default 1)

leishref install-ncbi-refseq
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install RefSeq (GCF) genomes only from NCBI::

    leishref install-ncbi-refseq
    leishref install-ncbi-refseq --force
    leishref install-ncbi-refseq --parallel 8

Filters out GenBank (GCA) duplicates, installing only the RefSeq-annotated genomes.
Uses accession as local alias. Same options and behavior as ``install-ncbi``.

Options:
- ``--force`` — Install again even if already installed
- ``--no-link`` — Skip alias-named symlinks
- ``--verbose`` — Show each install details (MD5, etc) instead of progress bar
- ``--parallel N`` — Download N genomes concurrently (default 1)

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

Returns all genomes matching all terms. A term may be a wildcard pattern
(``*``, ``?``, ``[...]``); quote it so the shell does not expand it first::

    leishref search 'GCF_*' infantum

leishref verify
~~~~~~~~~~~~~~~

Check integrity of local genomes::

    leishref verify
    leishref verify --quick

Verifies MD5 checksums. ``--quick`` checks presence only, skipping checksums.

leishref restore
~~~~~~~~~~~~~~~~~

Re-download every genome listed in ``accessions.txt`` in the current directory::

    leishref restore
    leishref restore --dry-run
    leishref restore --parallel 8

``leishref install`` appends every genome it installs to ``./accessions.txt`` as
``<catalog-id><TAB><alias>``. ``restore`` reads that file back and re-installs each
entry, so a database built on one machine can be rebuilt on another (or after the
local cache is cleared) with a single command. Genomes already installed are left
alone unless ``--force`` is given.

Options:
- ``--file PATH`` — Read from here instead of ``./accessions.txt``
- ``--force`` — Download again even if already installed
- ``--dry-run`` — List what would be downloaded and stop
- ``--from-installed`` — Write the file from what is already installed, then stop
- ``--verbose`` — Show each download in full instead of a progress bar
- ``--parallel N`` — Download N genomes concurrently (default 1)

leishref bundle
~~~~~~~~~~~~~~~~

Pack genomes into a ``.tar.gz``, either from the alias-named symlinks left in the
current directory or by genome name in the local database::

    leishref bundle '*.fna'
    leishref bundle 'Ld*.fna' 'Ltrop*.gff'
    leishref bundle Ld1S LdBPK
    leishref bundle 'Ld*' -o ld-all.tar.gz

A symlink pattern (matched against files in ``--basedir``, default ``.``) is resolved
to the real file it points at before archiving, so the tarball never contains bare
symlinks. A pattern or name that matches nothing on disk falls back to a genome-name
lookup in ``--local-dir``, with wildcard support via ``fnmatch``. Archiving from
symlinks keeps a flat layout (just the filename); archiving by genome name preserves
``<genome-id>/<filename>``.

Options:
- ``--local-dir PATH`` — Local database to search for genome names
- ``--basedir PATH`` — Directory to search for symlinks (default ``.``)
- ``--output PATH, -o PATH`` — Output tarball path (default ``bundle.tar.gz``)

leishref export
~~~~~~~~~~~~~~~~

Export genome metadata as JSON, YAML, or TSV::

    leishref export --format json
    leishref export --source both --format tsv -o catalog.tsv
    leishref export --source local --format yaml

Exports the catalog by default; ``--source local`` exports the cached database
instead, and ``--source both`` exports both. TSV flattens nested fields with dot
notation (e.g. ``stats.num_scaffolds``, ``files.fasta``), with a column union across
every exported genome since not all genomes carry the same optional fields.

Options:
- ``--source {catalog,local,both}`` — Which genomes to export (default ``catalog``)
- ``--format {json,yaml,tsv}`` — Output format (default ``json``)
- ``--output PATH, -o PATH`` — Write to a file instead of stdout

leishref plot-stats / plot-sizes / plot-histogram / plot-chromosome-histogram
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plotting utilities for publications, built from catalog statistics and (for the
chromosome histogram) locally available FASTA files::

    leishref plot-stats --output stats.png
    leishref plot-sizes --species donovani --species major
    leishref plot-histogram --include-kinetoplast
    leishref plot-chromosome-histogram --species tropica

- ``plot-stats`` — genome size, scaffold count, contig count, scaffold N50
- ``plot-sizes`` — genome sizes by species
- ``plot-histogram`` — distribution of genome sizes
- ``plot-chromosome-histogram`` — chromosome/sequence length distribution (requires
  the FASTA locally; sequences below 1 kb are excluded)

All four accept ``--catalog-dir`` and ``--output``; ``plot-sizes`` and
``plot-histogram`` also accept ``--include-kinetoplast`` to include kinetoplast-only
genomes (excluded by default as outliers).

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

Requires chromosome info in local database (populated during ``leishref dev fetch-genome`` from NCBI).
Rewrites FASTA file in-place and updates stored checksum.

leishref prune-scaffold
~~~~~~~~~~~~~~~~~~~~~~~

Remove unmapped contigs, keeping only chromosome sequences and kinetoplast::

    leishref prune-scaffold Ld1S

Removes sequences not found in chromosome database while automatically preserving
kinetoplast sequences (recognized by patterns: kinetoplast, maxicircle, maxi,
mitochondrion, etc.). Rewrites FASTA in-place and updates statistics.

Requires chromosome info in local database (populated during ``leishref dev fetch-genome``).

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

leishref dev fetch-genome
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a genome *assembly* from NCBI (GCA_/GCF_ accession, via the ``datasets`` CLI)::

    leishref dev fetch-genome GCA_000227135.2
    leishref dev fetch-genome GCA_000227135.2 --alias Ld1S

leishref dev fetch-nucleotide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a standalone NCBI nucleotide (nuccore) record - a single sequence that isn't
part of any GCA/GCF assembly, such as a lone kinetoplast/maxicircle::

    leishref dev fetch-nucleotide BK010877.1
    leishref dev fetch-nucleotide BK010877.1 --alias LiJPCM5.kinetoplast

Fetched via NCBI EUtils (through `bioservices
<https://bioservices.readthedocs.io/>`_) rather than the ``datasets`` CLI, since
``datasets`` only knows about assemblies. Written to
``leishref/data/ncbi_nucleotide/`` (``source: NCBI-Nucleotide``) rather than
``ncbi/``, since it's a different kind of record with a different fetch mechanism.

Options:
- ``--alias ALIAS`` — Also install into the local database under this name
- ``--species TEXT`` — Override the organism reported by NCBI
- ``--strain TEXT`` — Override the strain reported by NCBI
- ``--email TEXT`` — Contact email for NCBI EUtils (also settable in ``~/.config/bioservices/bioservices.cfg``)
- ``--force`` — Replace an existing catalog entry
- ``--no-link`` — Skip the alias-named symlink

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
