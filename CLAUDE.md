# Leishref Development Guide

## Catalog Directory Structure

**DO NOT MOVE directories around.** Catalog organization is fixed:

- `leishref/data/ncbi/` — NCBI reference genome *assemblies* (GCA_/GCF_ accessions)
- `leishref/data/ncbi_nucleotide/` — standalone NCBI nuccore records that are not a
  GCA/GCF assembly (e.g. a lone kinetoplast/maxicircle sequence). Fetched via
  `leishref dev fetch-nucleotide` (bioservices EUtils), not the `datasets` CLI used
  for `ncbi/`. `source: NCBI-Nucleotide`.
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

## Local Cache Is Keyed by Accession, Not Alias

`leishref install NAME --alias ALIAS` caches the genome under
`~/.config/leishref/<accession-or-catalog-identifier>/` - never under `<ALIAS>/`.
ALIAS only names the symlink `install` leaves in the current directory. This is
deliberate, not an implementation detail to "simplify":

- The cache is shared across every project on the machine. Keying it by alias meant
  two projects (or two `--alias` values) for the *same* genome each downloaded and
  stored a separate copy, and reusing an alias for a *different* genome was a real
  conflict requiring `--force` to resolve.
- Keying by accession/identifier instead means the same genome downloaded under any
  number of aliases shares one copy, and an alias can never collide with a
  different genome's cache entry - reusing one just repoints the symlink.

The genome's own `identifier` field is **never** rewritten to the alias (previously
`_install()` renamed it and stashed the original under
`provenance.catalog_id` - that mechanism is gone; `identifier` always stays what the
catalog says it is).

What a project calls a given accession only ever lives in **`./accessions.txt`**
(current directory, not the cache) as `<accession>\t<alias>` pairs. Anything that
needs to resolve a user-typed alias back to a cached genome - `info NAME`,
`bundle NAME`, `rename-sequences`, `prune-scaffold`, `dev publish`, `dev scaffold
--query/--reference` - goes through `_resolve_local()`/`_require_local()` in
`cli.py`, which checks the genome's own identity first and falls back to
`./accessions.txt`. `leishref link` and `restore --dry-run` resolve the *other*
direction (alias/name → cache dir) using `cache_key()` the same way `install` does.

`leishref dev add`/`dev scaffold` are unaffected in practice: they create a catalog
entry and its cache entry together under one name (no separate accession), so the
cache key and the alias are the same string by construction.

## Symlink Extension Standardization

All FASTA symlinks use `.fna` extension regardless of source:
- NCBI genomes: `.fna` (already standard)
- Scaffolds: `.fa` in catalog → symlink as `.fna`
- Custom/Zenodo: `.fasta`, `.fa`, or `.fna` → symlink as `.fna`

This ensures consistent naming for downstream tools. See `leishref/links.py:link_name()`.

## Bundle Command Behavior

`leishref bundle` supports two modes for creating tarballs:

### Mode 1: Symlink Resolution (file patterns in current directory)
```bash
leishref bundle '*.fna'                    # All .fna symlinks in current dir
leishref bundle 'Ld*.fna' 'Ltrop*.gff'    # Multiple patterns
```
- Finds symlinks matching pattern in current directory (or `--basedir`)
- Resolves symlinks to actual files in `~/.config/leishref`
- Archives with flat structure (just filename, no directory prefix)
- User sees only symlinks locally; bundle unpacks with actual files

### Mode 2: Genome Names (from leishref database)
```bash
leishref bundle Ld1S LdBPK                 # Exact genome IDs
leishref bundle 'Ld*'                      # Wildcard patterns
leishref bundle 'Ld*.fna' Ld1S            # Mix symlinks and IDs
```
- Looks up genome identifiers in local database
- Supports wildcard patterns with `fnmatch` (case-insensitive)
- Archives with directory structure: `genome-id/filename`
- Preserves provenance of where each file came from

### Implementation Notes
- Symlinks always checked first; fallback to genome lookup if no matches
- Deduplication: if both modes match same genome, included only once
- Default output: `bundle.tar.gz` (or use `-o/--output`)
- Uses `tarfile` with gzip compression

## Default code style & workflow

See `/home/cokelaer/CLAUDE.md` for global preferences (poetry, pytest, etc.).
