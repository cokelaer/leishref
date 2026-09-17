# Leishref Development Guide

## Catalog Directory Structure

**DO NOT MOVE directories around.** Catalog organization is fixed:

- `leishref/data/ncbi/` — NCBI reference genomes (GCA_/GCF_ accessions)
- `leishref/data/scaffolds/` — Scaffolds made from RefSeq genomes using ragtag
- `leishref/data/custom/` — All custom genomes, including experimental scaffolds (source="Custom", even if published on Zenodo)
- `leishref/data/tritrypdb/` — TriTrypDB genomes
- `leishref/data/zenodo/` — Zenodo-published genomes that are not custom or scaffolds

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

## Default code style & workflow

See `/home/cokelaer/CLAUDE.md` for global preferences (poetry, pytest, etc.).
