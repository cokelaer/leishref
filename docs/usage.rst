Usage
=====

Quick start
-----------

List the entire catalog::

    leishref info

Search for genomes::

    leishref search donovani

Download a genome locally::

    leishref install --alias Ld1S GCA_000227135.2

Verify checksums::

    leishref verify

User commands
-------------

.. code-block:: console

    $ leishref --help

    Usage: leishref [OPTIONS] COMMAND [ARGS]...

    Leishmania reference genome database.

    ╭─ Using the database ───────────────────────────────────────────────────────────────────────────────────────╮
    │ search                  Find catalog genomes matching every TERM.                                          │
    │ info                    List the catalog and the cached database, or show one genome in full.              │
    │ install                 Download a catalog genome and cache it with ALIAS.                                 │
    │ install-ncbi            Install all NCBI entries from the catalog.                                         │
    │ install-ncbi-refseq     Install all RefSeq (GCF) NCBI entries from the catalog.                            │
    │ restore                 Re-download every genome listed in accessions.txt in the current directory.        │
    │ verify                  Check the local database against the checksums recorded with each genome.          │
    │ rename-sequences        Rename sequences in a cached genome using chromosome database.                     │
    │ prune-scaffold          Remove unmapped contigs, keeping only chromosome sequences and kinetoplast.        │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ For maintainers and developers ───────────────────────────────────────────────────────────────────────────╮
    │ dev      Commands for maintaining the shipped catalog.                                                     │
    │ link     Refresh the alias-named symlinks for everything installed locally.                                │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ Plotting ─────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ plot-stats                Plot genome statistics: size, contig count, GC%.                                 │
    │ plot-sizes                Plot genome sizes by species.                                                    │
    │ plot-histogram            Plot histogram of genome sizes.                                                  │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ --help  Show this message and exit.                                                                        │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

For the dev part, use::

    leishref dev --help
