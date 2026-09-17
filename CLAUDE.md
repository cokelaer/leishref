# Leishref Development Guide

## Catalog Directory Structure

**DO NOT MOVE directories around.** Catalog organization is fixed:

- `leishref/data/ncbi/` — NCBI reference genomes (GCA_/GCF_ accessions)
- `leishref/data/scaffolds/` — Scaffolds made from RefSeq genomes using ragtag
- `leishref/data/custom/` — All custom genomes, including experimental scaffolds (source="Custom", even if published on Zenodo)
- `leishref/data/tritrypdb/` — TriTrypDB genomes

**Key rule:** If an entry has `source: Custom`, it stays in `custom/` regardless of whether it has Zenodo DOI or files. Do not reorganize by grouping logic—use the source field to determine placement.

### Example

```yaml
# Stays in custom/ because source: Custom (even with Zenodo DOI)
leishref/data/custom/Ltropica.Ld1S.scaffold.flye/metadata.yaml
identifier: Ltropica.Ld1S.scaffold.flye
source: Custom
provenance:
  zenodo_doi: 10.5281/zenodo.22710142
```

## Symlink Extension Standardization

All FASTA symlinks use `.fna` extension regardless of source:
- NCBI genomes: `.fna` (already standard)
- Scaffolds: `.fa` in catalog → symlink as `.fna`
- Custom/Zenodo: `.fasta`, `.fa`, or `.fna` → symlink as `.fna`

This ensures consistent naming for downstream tools. See `leishref/links.py:link_name()`.

## Default code style & workflow

See `/home/cokelaer/CLAUDE.md` for global preferences (poetry, pytest, etc.).
