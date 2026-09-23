Usage
=====

Quick start
-----------

List the entire catalog::

    leishref info

Show details for one genome::

    leishref info GCA_037177955.1

Search for genomes::

    leishref search donovani

Download a genome locally::

    leishref install GCA_000227135.2 --alias Ld1S

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
    │ install                 Download a catalog genome and cache it, with a symlink named ALIAS.                 │
    │ install-ncbi            Install all NCBI entries from the catalog.                                         │
    │ install-ncbi-refseq     Install all RefSeq (GCF) NCBI entries from the catalog.                            │
    │ restore                 Re-download every genome listed in accessions.txt in the current directory.        │
    │ verify                  Check the local database against the checksums recorded with each genome.          │
    │ rename-sequences        Rename sequences in a cached genome using chromosome database.                     │
    │ prune-scaffold          Remove unmapped contigs, keeping only chromosome sequences and kinetoplast.        │
    │ bundle                  Pack genomes into a tarball: from symlinks or by genome name.                      │
    │ export                  Export genome metadata as JSON, YAML, or TSV.                                      │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ For maintainers and developers ───────────────────────────────────────────────────────────────────────────╮
    │ dev      Commands for maintaining the shipped catalog.                                                     │
    │ link     Refresh the alias-named symlinks for everything installed from here.                              │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ Plotting ─────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ plot-stats                   Plot genome statistics: genome size, scaffold count, contig count, scaffold   │
    │                              N50.                                                                          │
    │ plot-sizes                   Plot genome sizes by species.                                                 │
    │ plot-histogram               Plot histogram of genome sizes.                                               │
    │ plot-chromosome-histogram    Plot chromosome/sequence length histogram from available local FASTA files.   │
    │ plot-completeness            Plot pie chart of genome completeness (assembly_level breakdown).             │
    │ plot-technology              Plot pie chart of sequencing technology distribution.                         │
    │ plot-assembly-by-technology  Plot assembly level (quality) vs sequencing technology.                        │
    │ plot-species-count           Plot bar chart of genome count per species.                                   │
    │ plot-gc-content              Plot GC content distribution by species.                                      │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ --version  Show the version and exit.                                                                      │
    │ --help     Show this message and exit.                                                                     │
    ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

For the dev part, use::

    leishref dev --help
