Catalog
=======

Structure
---------

The leishref catalog ships inside the package under ``leishref/data/``. Entries are
grouped by where the genome came from, and each genome then has its own directory,
named by accession for NCBI genomes and by alias for everything else::

    leishref/data/
    ├── aliases.txt
    ├── ncbi/
    │   ├── GCA_000227135.2/
    │   │   └── metadata.yaml
    │   └── GCA_000410715.1/
    │       └── metadata.yaml
    ├── scaffold/
    │   └── Ltropica.Ld1S.scaffold.flye/
    │       └── metadata.yaml
    ├── tritrypdb/
    │   └── TriTrypDB-68_LamazonensisPH8/
    │       └── metadata.yaml
    └── zenodo/

``leishref dev fetch`` and ``leishref dev import`` write into ``ncbi/``,
``leishref dev scaffold`` into ``scaffold/``, and a TriTrypDB or Zenodo genome into the
directory of the same name. Grouping follows how a genome was *made*, not where its
files currently live: ``leishref dev publish`` deposits a scaffold on Zenodo and records
the DOI, but the entry stays under ``scaffold/`` rather than moving.

A flat layout is still read, so a local database (``data/<alias>/``) and any catalog
written before the grouping are both loaded without change.

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

**Aliases are not frozen.** They may change to fix typos, adopt better naming conventions,
or reflect biology more clearly. When you download a genome with a catalog alias (e.g.,
``leishref download --alias Ld1S Ld1S``), the actual accession (e.g., ``GCA_000227135.2``)
is recorded in ``accessions.txt``. Restoring from ``accessions.txt`` retrieves the same
genome by accession, which is stable—but a re-download might assign it a different alias
if ``aliases.txt`` changed. For reproducible scripts, refer to genomes by accession, not
by alias.

Updating the catalog
---------------------

Add a new genome::

    leishref dev fetch --accession <GCA_ID>

The catalog is version-controlled in git. Commit metadata changes::

    git add leishref/data/ncbi/<accession>/metadata.yaml
    git commit -m "Add genome <accession>"
