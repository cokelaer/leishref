Install
=======

Installing genomes locally
---------------------------

Install a genome from the catalog::

    leishref install --alias MyStrain GCA_000227135.2

This creates a local directory ``data/MyStrain/`` with the genome FASTA and GFF.

Using aliases
-------------

Common reference strains have built-in aliases::

    leishref install --alias Ld1S Ld1S
    leishref install --alias LdHU3 LdHU3
    leishref install --alias LtL590 LtL590

Verification
------------

All installs are verified against recorded MD5 checksums::

    leishref verify

Local database
--------------

Genomes are stored under ``data/<alias>/`` relative to where you run leishref (default).
Customize the location with ``--local-dir``::

    leishref install --local-dir /mnt/genomes/data --alias Ld1S GCA_002243465.1

Each genome has:

- ``*.fna`` — FASTA sequence
- ``*.gff`` — Genome features
- ``metadata.yaml`` — Provenance and statistics

Recording what was installed
----------------------------

Every ``leishref install`` appends a line to ``<local-dir>/accessions.txt``::

    # Genomes installed with 'leishref install', most recent last.
    # Format: catalog-identifier<TAB>alias    Replay with 'leishref restore'.
    GCA_002243465.1	Ld1S
    GCF_000002875.2	LiJPCM5

The catalog identifier (accession) is stored as the source of truth, since aliases are
not stable. ``leishref/data/aliases.txt`` may change to fix typos, use better naming
conventions, or reflect biology more clearly. When you run ``leishref restore``, genomes
are installed by their accessions (which never change); the alias they
are given locally may differ from what was originally typed if ``aliases.txt`` changed in
the meantime. Each genome appears once in ``accessions.txt``: re-installing it overwrites
its line.

Rebuilding a database
---------------------

``leishref restore`` installs everything listed in that file, which rebuilds the
same local database on another machine or after ``data/`` has been cleared::

    leishref restore --dry-run     # list what is missing, install nothing
    leishref restore               # install whatever is not there yet
    leishref restore --force       # install everything again
    leishref restore --file ../TEST2/data/accessions.txt

Restoring shows a progress bar rather than the output of each install::

    Ltrop.ncbi.L590:  62%|######2   | 5/8 [01:12<00:41, 13.8s/genome]

What an install printed is kept back and shown only for the genomes that failed, where
it is the diagnosis. ``--verbose`` turns the bar off and prints every install in full.
The bar goes to stderr and switches itself off when that is not a terminal, so piping
or redirecting a restore stays clean.

Genomes already installed are left alone unless ``--force`` is given, and one genome
that fails to install does not stop the others; the command exits non-zero and names
the aliases that failed.

A database created before this file existed can describe itself, since every installed
genome records the catalog entry it came from::

    leishref restore --from-installed
