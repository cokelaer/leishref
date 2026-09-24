# Publication Plan

## Target Journals

**Primary:** PLoS Neglected Tropical Diseases
- Prestige, high reach in Leishmania community
- Slower review (~6 months)

**Secondary:** Parasites & Vectors
- Faster turnaround (~3-4 months)
- Strong parasitology readership
- Also good impact

Both open access.

## Paper Type

Resource/Methods paper

## Key Messages

- **Problem:** Leishmania reference genomes in NCBI/TriTrypDB lack provenance tracking; strain aliases inconsistent; community cannot reliably reproduce analyses
- **Solution:** leishdb — local database with stable strain aliases, accession tracking, WHO nomenclature, metadata catalog
- **Impact:** Reproducibility for phylogenomics, comparative genomics, scaffold-based assembly workflows

## Scope

- Database architecture (why local, not API)
- Alias and accession system
- Metadata catalog structure
- CLI usage for install/verify/query
- 156 reference genomes catalogued
- Case study: scaffold genome naming and reproducibility

## What to Include

- Methods: genome source (NCBI RefSeq, TriTrypDB), metadata extraction, WHO strain nomenclature
- Results: catalog stats, alias stability guarantees, accession-based reproducibility demo
- Availability: GitHub, poetry/pip install
- Supplementary: aliases.txt format, catalog.json schema
