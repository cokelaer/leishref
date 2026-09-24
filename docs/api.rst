Python API
==========

Working with metadata
---------------------

Load a genome from the catalog::

    from leishref.metadata import catalog, find

    genomes = catalog()
    genome = find(genomes, "Ld1S")
    print(genome.species, genome.strain)

Load local genomes::

    from leishref.metadata import local

    installed = local()
    for genome in installed:
        print(genome.identifier)

Searching
---------

Search for genomes::

    genomes = [g for g in catalog() if g.matches(["donovani", "reference"])]

Checksums
---------

Verify checksums::

    from leishref.checksums import verify_file

    path = "data/Ld1S/GCA_000227135.2_ASM22713v2_genomic.fna"
    md5_recorded = "d41d8cd98f00b204e9800998ecf8427e"

    if verify_file(path, md5_recorded):
        print("OK")

Aliases
-------

Resolve aliases::

    from leishref.metadata import load_aliases, find

    aliases = load_aliases()
    genomes = catalog()
    genome = find(genomes, "Ld1S")  # resolves via alias

Module Reference
----------------

.. automodule:: leishref.metadata
   :members:

.. automodule:: leishref.checksums
   :members:

.. automodule:: leishref.links
   :members:
