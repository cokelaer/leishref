Search
======

Finding genomes
---------------

Search the catalog by species name, strain, accession, or alias::

    leishref search donovani
    leishref search LdHU3
    leishref search GCA_000227135.2

Search results show::

- Genome identifier (alias or name)
- Species and strain
- NCBI accession
- Catalog alias (if available)

Multiple terms are AND-ed together::

    leishref search donovani major

Wildcards
---------

A term may be a shell-style pattern (``*``, ``?``, ``[...]``). Quote it, otherwise the
shell expands it against the files in the current directory before ``leishref`` sees it::

    leishref search '*'                 # the whole catalog
    leishref search 'GCF_*'             # RefSeq copies only
    leishref search 'GCA_0002*' infantum
    leishref search 'L*tropica'

Terms without a wildcard keep matching as substrings, so ``leishref search tropic``
still finds *Leishmania tropica*.

GenBank and RefSeq
------------------

NCBI publishes most assemblies twice: the submitter's GenBank copy (``GCA_``) and NCBI's
own RefSeq copy (``GCF_``). Both are in the catalog, with the same assembly name and the
same statistics but different sequence names, checksums and annotation. The source column
of a search result says which one a row is::

    GCA_000002875.2  Leishmania infantum - JPCM5  GenBank  2011  Chromosome  32.1 Mb
    GCF_000002875.2  Leishmania infantum - JPCM5  RefSeq   2011  Chromosome  32.1 Mb
