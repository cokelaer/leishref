# Leishmania Genome Database

Manage Leishmania genomes from NCBI, TriTrypDB, and custom assemblies with provenance tracking, aliasing, and automated scaffolding.

## Installation

```bash
poetry install
```

## Quick Start

### Backfill existing files into manifest

```bash
leish-backfill --dry-run  # preview
leish-backfill            # actually add
```

### Fetch a genome from NCBI

```bash
leish-fetch --accession GCA_000410715.1 --alias Ltropica.L590
```

### Scaffold a query against a reference

```bash
leish-scaffold --query MyAssemblies/LtropicaCDC/query.fasta --reference Ld1S --clean --alias Ltropica.CDC
```

### View manifest

```bash
leish-info
leish-info --alias Ltropica.L590
```

## Database Structure

- `manifest.csv` — master index with provenance (git-tracked)
- `aliases.csv` — user aliases mapping (git-tracked)
- `NCBI/` — raw NCBI downloads
- `TriTryDB68/` — TriTrypDB release 68 downloads
- `MyAssemblies/` — custom assemblies
- `Scaffold/` — ragtag outputs
- `leishdb/` — Python package
- `tests/` — test suite

## Manifest Columns

- `filename`, `gff_filename` — file paths
- `source` — NCBI, TriTrypDB, MyAssembly, Scaffold
- `accession`, `assembly_name`, `release_version`
- `species`, `strain`, `alias`
- `md5sum_fasta`, `md5sum_gff` — checksums
- `scaffold_reference_alias`, `scaffold_tool_version` — scaffold metadata
- `cleaned` — True if pruned to chr-anchored + kinetoplast
- `cleaned_from` — reference to original scaffold row
- `zenodo_doi` — published deposition DOI
- `sequencing_technology`, `bioproject`, `biosample`, `raw_reads_accession` — NCBI metadata
- `date_added`, `notes`

## Development

```bash
pytest --cov=leishdb
pre-commit run --all-files
```
