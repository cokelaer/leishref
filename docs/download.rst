Download
========

Installing genomes locally
---------------------------

Download a genome from the catalog::

    leishref download --alias MyStrain GCA_000227135.2

This creates a local directory ``data/MyStrain/`` with the genome FASTA and GFF.

Using aliases
-------------

Common reference strains have built-in aliases::

    leishref download --alias Ld1S Ld1S
    leishref download --alias LdHU3 LdHU3
    leishref download --alias LtL590 LtL590

Verification
------------

All downloads are verified against recorded MD5 checksums::

    leishref verify

Local database
--------------

Genomes are stored under ``data/<alias>/`` relative to where you run leishref.
Each genome has:

- ``*.fna`` — FASTA sequence
- ``*.gff`` — Genome features
- ``metadata.yaml`` — Provenance and statistics
