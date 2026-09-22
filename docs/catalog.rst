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
    ├── ncbi_nucleotide/
    │   └── BK010877.1/
    │       └── metadata.yaml
    ├── scaffold/
    │   └── Ltropica.Ld1S.scaffold.flye/
    │       └── metadata.yaml
    ├── tritrypdb/
    │   └── TriTrypDB-68_LamazonensisPH8/
    │       └── metadata.yaml
    └── zenodo/

``leishref dev fetch-genome`` writes into ``ncbi/``, ``leishref dev scaffold`` into
``scaffold/``, ``leishref dev add`` + ``leishref dev publish`` into ``custom/``, and
a TriTrypDB or Zenodo genome into the directory of the same name. Grouping follows
how a genome was *made*, not where its files currently live: publishing a scaffold
deposits it on Zenodo and records the DOI, but the entry stays under ``scaffold/``
rather than moving - likewise a ``custom/`` entry stays there even once published.

``ncbi/`` is for GCA/GCF *assemblies*, fetched with NCBI's ``datasets`` CLI.
``ncbi_nucleotide/`` is for a standalone NCBI nuccore record that isn't part of any
assembly - typically a single sequence such as a kinetoplast/maxicircle deposited on
its own - fetched instead via ``leishref dev fetch-nucleotide`` over NCBI EUtils
(through `bioservices <https://bioservices.readthedocs.io/>`_).

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
    LtrL590	GCA_000410715.1
    LdMHOM_BR_75_M2904	GCA_000002845.2

Alias format: species code (L + 1-2 letters: Ld, Lm, Li, Ltr, etc.) plus strain discriminator
(e.g., ``1S``, ``BPK``, ``L590``). WHO strain nomenclature is preserved when available:
``MHOM`` = mammalian human origin (e.g., ``MHOM/BR/75/M2904``: Brazil, 1975, human isolate);
``MCAN`` = canine; ``MCEB`` = other mammal; ``MDAS`` = rodent. The full format
``HOST/COUNTRY/YEAR/ID`` encodes epidemiology and is retained in aliases for traceability.

Use aliases in search, install, and info commands.

**Aliases are not frozen.** They may change to fix typos, adopt better naming conventions,
or reflect biology more clearly. When you install a genome with a catalog alias (e.g.,
``leishref install --alias Ld1S Ld1S``), the actual accession (e.g., ``GCA_000227135.2``)
is recorded in ``accessions.txt``. Restoring from ``accessions.txt`` retrieves the same
genome by accession, which is stable—but a re-install might assign it a different alias
if ``aliases.txt`` changed. For reproducible scripts, refer to genomes by accession, not
by alias.

Updating the catalog
---------------------

Add a new genome::

    leishref dev fetch-genome <GCA_ID>

The catalog is version-controlled in git. Commit metadata changes::

    git add leishref/data/ncbi/<accession>/metadata.yaml
    git commit -m "Add genome <accession>"
