Metadata Schema
===============

Each genome has a ``metadata.yaml`` file storing provenance and statistics.

Core fields
-----------

**identifier** (string)
    Human-readable name (e.g., ``Ld1S``).

**source** (string)
    Origin: ``ncbi``, ``tritrypdb``, ``zenodo``, or ``scaffold``.

**accession** (string)
    NCBI assembly accession (e.g., ``GCA_000227135.2``).

**taxon_id** (int)
    NCBI Taxonomy ID (e.g., ``5671`` for *Leishmania donovani*).

**species** (string)
    Full species name (e.g., ``Leishmania donovani``).

**strain** (string)
    Strain name (e.g., ``1S``, ``HU3``).

**assembly_name** (string)
    NCBI assembly name (e.g., ``ASM22713v2``).

**assembly_level** (string)
    Completeness: ``chromosome``, ``scaffold``, ``contig``.

**release_date** (date)
    Date assembled (ISO 8601 format).

Files
-----

**files.fasta** (string)
    FASTA filename.

**files.gff** (string)
    GFF filename.

Checksums
---------

**checksums.fasta** (hex string)
    MD5 hash of FASTA.

**checksums.gff** (hex string)
    MD5 hash of GFF.

Statistics
----------

**stats.num_scaffolds** (int)
    Number of scaffolds.

**stats.scaffold_n50** (int)
    Scaffold N50 length.

**stats.gc_percent** (float)
    GC content (0–100).

**stats.num_contigs** (int)
    Number of contigs.

Provenance
----------

**provenance.catalog_id** (string)
    Original catalog reference.

**provenance.ncbi_bioproject** (string)
    NCBI BioProject ID.

**provenance.zenodo_doi** (string)
    Zenodo DOI.

**provenance.sequencing_technology** (string)
    ``illumina``, ``pacbio``, ``nanopore``, etc.

Example
-------

.. code-block:: yaml

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
      num_contigs: 1024
      gc_percent: 52.3
    provenance:
      catalog_id: GCA_000227135.2
      ncbi_bioproject: PRJNA12345
      sequencing_technology: illumina
