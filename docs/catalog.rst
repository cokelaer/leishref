Catalog
=======

Structure
---------

The leishref catalog ships inside the package under ``leishref/data/``.
Each genome has its own directory named by NCBI accession::

    leishref/data/
    ├── GCA_000227135.2/
    │   └── metadata.yaml
    ├── GCA_000410715.1/
    │   └── metadata.yaml
    └── ...

Metadata schema
---------------

Each ``metadata.yaml`` contains::

    identifier: Ld1S
    source: ncbi
    accession: GCA_000227135.2
    taxon_id: 5671
    species: Leishmania donovani
    strain: 1S
    assembly_name: ASM22713v2
    assembly_level: chromosome
    release_date: 2011-05-13
    files:
      fasta: GCA_000227135.2_ASM22713v2_genomic.fna
      gff: GCA_000227135.2_ASM22713v2_genomic.gff
    checksums:
      fasta: d41d8cd98f00b204e9800998ecf8427e
      gff: d41d8cd98f00b204e9800998ecf8427e
    stats:
      num_scaffolds: 36
      scaffold_n50: 2500000
      gc_percent: 52.3
    provenance:
      ncbi_bioproject: PRJNA12345
      catalog_id: GCA_000227135.2

Aliases
-------

Common reference strains have shorthand aliases in ``leishref/data/aliases.txt``::

    LdHU3	GCA_900635355.2
    Ld1S	GCA_000227135.2
    LtL590	GCA_000410715.1

Use aliases in search, download, and info commands.

Updating the catalog
---------------------

Add a new genome::

    leishref dev fetch --accession <GCA_ID>

The catalog is version-controlled in git. Commit metadata changes::

    git add leishref/data/<accession>/metadata.yaml
    git commit -m "Add genome <accession>"
