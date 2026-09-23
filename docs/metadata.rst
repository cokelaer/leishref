Metadata Schema
===============

Each genome has a ``metadata.yaml`` file storing provenance and statistics.

Core fields
-----------

**identifier** (string)
    Human-readable name (e.g., ``Ld1S``).

**source** (string)
    Origin: ``ncbi``, ``ncbi_nucleotide``, ``tritrypdb``, ``zenodo``, or ``scaffold``.
    ``ncbi_nucleotide`` is a standalone NCBI nuccore record (e.g. a lone kinetoplast
    sequence) rather than a GCA/GCF assembly - see :doc:`catalog`.

**accession** (string)
    NCBI assembly accession (e.g., ``GCA_000227135.2``), or a nuccore accession (e.g.,
    ``BK010877.1``) when ``source`` is ``ncbi_nucleotide``.

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

**molecule_type** (string, optional)
    What this entry actually is, when it isn't an ordinary nuclear assembly - e.g.
    ``kinetoplast``, or ``kinetoplast,maxicircle``. Unset for ordinary nuclear genomes.
    NCBI's own ``assembly_level`` doesn't distinguish this - a lone maxicircle
    submitted as a "genome assembly" still comes back as e.g. ``Chromosome`` - so
    nothing infers it automatically; set it by hand with ``--molecule-type`` on
    ``dev fetch-genome``, ``dev fetch-nucleotide``, or ``dev add``. Included in
    :doc:`search`, so ``leishref search kinetoplast`` finds anything tagged this way
    regardless of species or accession.

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

Scaffolded assemblies
---------------------

An assembly produced by ``leishref dev scaffold`` records both parents, so the result
can be reproduced and the two inputs recognised later by checksum.

The identifier follows the pattern ``<query_alias>.scaffold.<ref_alias>``, which is
auto-generated when ``--alias`` is omitted. For TriTrypDB genomes, the alias includes
a ``_tritryp`` suffix to avoid collision with NCBI genomes. Species codes use single
letters where unambiguous (Ld, Lm, Li) and two letters where ambiguous (Ltr, Lta, Ltu)::

    identifier: LtrL590.scaffold.Ld1S
    source: Scaffold
    species: Leishmania tropica       # the query, not the reference
    strain: L590
    assembly_level: Scaffold
    scaffold:
      query:
        file: GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna
        md5: 2f1c...
        name: GCA_000410715.1
        species: Leishmania tropica
        strain: L590
      reference:
        file: GCA_002243465.1_ASM224346v1_genomic.fna
        md5: ce46...
        name: GCA_002243465.1
        species: Leishmania donovani
        strain: Ld1S
        assembly_level: Chromosome
      tool: RagTag
      tool_version: 2.1.0
      cleaned: true

**scaffold.query** / **scaffold.reference** (mapping)
    What went in. ``name`` is the catalog identifier rather than a local alias, since an
    alias can be renamed while the identifier stays valid; ``md5`` identifies the exact
    file used. A parent given as a bare FASTA path has only ``file`` and ``md5``.

**scaffold.tool**, **scaffold.tool_version** (string)
    The scaffolder and the version it reported, read from the binary at run time.

**scaffold.cleaned** (bool)
    Present when ``--clean`` was used, meaning only chromosome-anchored contigs and the
    kinetoplast were kept.

Species and strain describe the query. Scaffolding *L. tropica* onto an *L. donovani*
reference yields an *L. tropica* assembly; the reference appears only under
``scaffold.reference``. When the query is a bare FASTA there is nothing to take this
from, so ``--species`` and ``--strain`` are required.

Entries written before this naming scheme use ``--alias`` for custom names or flat
``scaffold.reference_alias`` and are left as they are.

Publishing scaffolds
--------------------

Scaffolds created with ``leishref dev scaffold`` live in the local database initially.
To make them available for sharing, use ``leishref dev publish``:

1. Create and install the scaffold::

    leishref dev scaffold --query LtrL590 --reference Ld1S

2. Publish to Zenodo (uploads both FASTA and AGP)::

    leishref dev publish LtrL590.scaffold.Ld1S --confirm --version v1.0

3. The command records the DOI and updates both the local copy and the catalog entry,
   so the scaffold appears in ``leishref info`` with a ``zenodo`` marker.

For testing, use ``--sandbox`` to publish to sandbox.zenodo.org first::

    leishref dev publish LtrL590.scaffold.Ld1S --confirm --sandbox
