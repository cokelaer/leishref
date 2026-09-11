# Leishmania Reference Genome Database (leishref)

Manage Leishmania genomes from NCBI, TriTrypDB, and custom assemblies with full provenance tracking, user-friendly aliasing, and automated ragtag scaffolding.

**Key features:**
- Single `manifest.csv` index tracking all genomes with source, accession, md5sums, sequencing metadata
- User aliases for easy reference (e.g., `Ld1S` instead of full filename)
- NCBI-first strategy: fetch from NCBI, fall back to TriTrypDB if missing, cross-check length if both exist
- Ragtag scaffolding with AGP-based cleaning to remove unplaced contigs while preserving chromosome-anchored sequences and kinetoplast (maxicircle/kDNA)
- Per-scaffold Zenodo publishing for reproducible DOI provenance
- Git-tracked code + manifest; sequence data on disk (ignored by git)

---

## Installation & Setup

### Prerequisites
- Python 3.9+
- Poetry (for dependency management)
- `datasets` CLI from NCBI (via damona `sequana_tools` env, or standalone)
- `ragtag.py` (currently in py311 conda env; will auto-locate or specify with `--ragtag-bin`)

### Install

```bash
# Clone/navigate to repo
cd /path/to/Leishmania

# Install dependencies
poetry install

# Verify CLI is available
leishref backfill --help
```

---

## Database Structure

```
Leishmania/
├── manifest.csv              # Master index (git-tracked) — all genomes + metadata
├── aliases.csv               # User-defined aliases (git-tracked) — e.g., Ld1S → Ld1S.fa
├── NCBI/                     # Raw NCBI downloads (fasta + gff, prefix-matched pairs)
│   ├── Ld1S.fa
│   └── Ld1S.gff
├── TriTryDB68/               # TriTrypDB release-68 downloads (fallback source)
├── MyAssemblies/             # Custom/own assemblies (pre-scaffold, not git-tracked)
│   └── LtropicaCDC/
│       ├── Ltropica.Ld1S.scaffold.flye.fasta
│       ├── Ltropica.Ld1S.scaffold.pecat.fasta
│       └── README.rst
├── Scaffold/                 # Ragtag outputs (not git-tracked)
│   ├── Species.Strain.on.RefAlias.fa
│   ├── Species.Strain.on.RefAlias.agp
│   ├── Species.Strain.on.RefAlias.cleaned.fa  # Pruned version (chrom-anchored only)
│   └── ...
├── leishref/                  # Python package (git-tracked)
│   ├── __init__.py
│   ├── manifest.py           # CSV I/O
│   ├── aliases.py            # Alias resolution
│   ├── checksums.py          # md5/sequence_length/contig_count
│   ├── ncbi.py               # datasets CLI wrapper
│   ├── tritrypdb.py          # TriTrypDB release-68 download
│   ├── scaffold.py           # ragtag wrapper + AGP cleaning
│   ├── zenodo.py             # Zenodo deposition management
│   └── cli.py                # CLI entry points
├── tests/                    # Test suite (git-tracked)
│   ├── test_manifest.py
│   ├── test_aliases.py
│   └── test_scaffold_clean.py
├── pyproject.toml            # Poetry config (git-tracked)
└── .gitignore                # Ignore sequence data, pycache, etc.
```

---

## Manifest Schema

Single CSV with 22 columns, one row per genome/scaffold:

| Column | Type | Description |
|--------|------|-------------|
| `filename` | str | Fasta filename (relative path) |
| `gff_filename` | str | GFF filename (relative path, may be empty) |
| `source` | str | NCBI, TriTrypDB, MyAssembly, Scaffold |
| `accession` | str | NCBI/TriTrypDB accession (e.g., GCA_000410715.1) |
| `assembly_name` | str | Full assembly name from NCBI |
| `release_version` | str | Release/version tag |
| `species` | str | Genus species (e.g., Leishmania_major) |
| `strain` | str | Strain name (e.g., Friedlin) |
| `alias` | str | User alias for easy lookup |
| `md5sum_fasta` | str | Checksum of fasta file |
| `md5sum_gff` | str | Checksum of GFF file |
| `scaffold_reference_alias` | str | Alias of reference used for scaffolding |
| `scaffold_tool_version` | str | ragtag.py version |
| `cleaned` | bool | True if pruned to chr-anchored + kinetoplast |
| `cleaned_from` | str | Filename of original (unclean) scaffold |
| `zenodo_doi` | str | Zenodo deposition DOI (if published) |
| `sequencing_technology` | str | Sequencing method from NCBI metadata |
| `bioproject` | str | NCBI BioProject accession |
| `biosample` | str | NCBI BioSample accession |
| `raw_reads_accession` | str | SRA accession for raw reads |
| `date_added` | str | ISO date added to DB |
| `notes` | str | Free-text notes (e.g., "backfilled from disk", "length differs from <other>") |

---

## Aliases

Simple CSV: `alias, target`. Target is typically a filename or NCBI accession.

```csv
alias,target
Ld1S,Ld1S.fa
Ltropica.L590,GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna
Ltropica.CDC,MyAssemblies/LtropicaCDC/Ltropica.Ld1S.scaffold.flye.fasta
```

User adds/edits aliases; CLI resolves them. E.g., `--reference Ld1S` looks up alias in CSV.

---

## Quick Start

### 1. Backfill existing files (one-time setup)

Scan disk for existing NCBI, MyAssemblies, and Scaffold files; compute md5sums; populate manifest.

```bash
# Preview what will be added
leishref backfill --dry-run

# Actually add to manifest.csv
leishref backfill

# Check manifest
leishref info
```

Example output:
```
Scanning NCBI/...
  Ld1S.fa
Scanning MyAssemblies/...
  Ltropica.Ld1S.scaffold.pecat.fasta
  Ltropica.Ld1S.scaffold.flye.fasta
  ...
Added 5 rows to manifest
```

### 2. Fetch a genome from NCBI

Downloads fasta + GFF from NCBI using `datasets` CLI; extracts metadata (sequencing tech, BioProject, BioSample); appends manifest row.

```bash
# Fetch *L. tropica* L590 from NCBI
leishref fetch \
  --accession GCA_000410715.1 \
  --species Leishmania_tropica \
  --strain L590 \
  --alias Ltropica.L590

# Check result
leishref info --alias Ltropica.L590
```

Files created:
- `NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna` (fasta)
- `NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.gff` (GFF)
- Manifest row added with source=NCBI, md5sums, metadata

### 3. Scaffold a query against a reference

Run ragtag to scaffold query fasta against reference; optionally clean (prune unplaced contigs).

```bash
# Scaffold query onto Ld1S reference
leishref scaffold \
  --query MyAssemblies/LtropicaCDC/assembly.fasta \
  --reference Ld1S \
  --alias Ltropica.CDC.onLd1S \
  --clean

# Files created
# Scaffold/Ltropica.CDC.onLd1S.fa       (original ragtag output)
# Scaffold/Ltropica.CDC.onLd1S.agp      (AGP file from ragtag)
# Scaffold/Ltropica.CDC.onLd1S.cleaned.fa  (chr-anchored + maxicircle only)
```

**Cleaning details:**
- Parses `ragtag.scaffold.agp` to identify which contigs were placed on reference chromosomes
- Removes unplaced contigs (gaps, orphans)
- **Preserves** maxicircle/kinetoplast (matched by name pattern) — important for Leishmania!
- Original `.fa` and `.cleaned.fa` both tracked in manifest

### 4. Publish a scaffold to Zenodo

Create a Zenodo deposition for a single scaffold (fasta + AGP), upload, publish, and get DOI.

```bash
# Dry-run (preview)
leishref publish --scaffold Scaffold/Ltropica.CDC.onLd1S.fa

# Actually publish (requires ZENODO_TOKEN env var)
export ZENODO_TOKEN="your-zenodo-api-token"
leishref publish --scaffold Scaffold/Ltropica.CDC.onLd1S.fa --confirm
```

Result:
- Deposition created on Zenodo with metadata (title, description, creators)
- Files uploaded (`.fa` + `.agp`)
- Published (made public) with DOI
- DOI written back to manifest.csv in `zenodo_doi` column

### 5. Look up in manifest

```bash
# All genomes
leishref info

# Single alias
leishref info --alias Ld1S

# Output:
# filename: Ld1S.fa
# source: NCBI
# accession: GCA_000410715.1
# species: Leishmania_donovani
# alias: Ld1S
# ...
```

---

## Data Source Priority

1. **NCBI** (primary) — try to fetch fasta + GFF
2. **TriTrypDB** (fallback) — if not on NCBI
3. **Cross-check** — if both exist:
   - Compare total assembly length
   - Match → keep NCBI row only, note "TriTrypDB skipped, length matches NCBI"
   - Differ → keep both rows, cross-reference in notes (e.g., "length differs from GCA_...")

---

## Workflow Examples

### Add a known NCBI genome + scaffold onto Ld1S reference

```bash
# 1. Fetch from NCBI
leishref fetch --accession GCA_000410715.1 --alias Ltropica.L590

# 2. Scaffold onto Ld1S (assumes Ld1S alias exists and points to NCBI/Ld1S.fa)
leishref scaffold \
  --query NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna \
  --reference Ld1S \
  --clean \
  --alias Ltropica.L590.onLd1S

# 3. Publish scaffold to Zenodo
export ZENODO_TOKEN="..."
leishref publish --scaffold Scaffold/Ltropica.L590.onLd1S.fa --confirm

# 4. View manifest
leishref info
```

### Backfill existing custom assembly + check

```bash
# 1. Put assembly in MyAssemblies/MyStrain/
mkdir -p MyAssemblies/MyStrain
cp ~/my_assembly.fasta MyAssemblies/MyStrain/

# 2. Backfill
leishref backfill

# 3. Edit aliases.csv to add short name
# Add: MyStrain,MyAssemblies/MyStrain/my_assembly.fasta

# 4. Scaffold onto reference
leishref scaffold --query MyAssemblies/MyStrain/my_assembly.fasta --reference Ld1S --clean --alias MyStrain.onLd1S
```

---

## Development

### Run tests (manual, pytest env issue with conda py311)

```bash
# Via python directly
python3 -c "
import tempfile
from pathlib import Path
from leishref.manifest import Manifest, ManifestRow

with tempfile.TemporaryDirectory() as tmpdir:
    m = Manifest(Path(tmpdir) / 'test.csv')
    m.append(ManifestRow(filename='test.fa', source='NCBI'))
    assert len(m.read()) == 1
    print('Test passed!')
"
```

### Lint & format

```bash
# Per CLAUDE.md defaults
black --line-length=120 leishref/ tests/
isort --profile=black leishref/ tests/
flake8 leishref/ tests/
```

### Add a new source

Edit `leishref/fetch.py` (orchestrator) to handle new source. Add new module (e.g., `leishref/newsource.py`) with download function.

---

## Troubleshooting

**ragtag.py not found:**
- Set `--ragtag-bin /path/to/ragtag.py` in scaffold command
- Or install into active conda env: `conda install ragtag`

**datasets CLI not available:**
- `damona activate sequana_tools` before running `leish-fetch`

**NCBI accession not found:**
- Verify accession format (e.g., GCA_000410715.1)
- Check NCBI GenBank directly
- Falls back to TriTrypDB if available

**Zenodo auth fails:**
- Verify `ZENODO_TOKEN` is set and valid
- Get token from https://zenodo.org/account/settings/applications/tokens/new

---

## Citation & Attribution

Generated with [Claude Code](https://claude.com/claude-code). See git log for commit history and rationale.

If publishing data from this DB, cite original NCBI/TriTrypDB sources and Zenodo DOIs from manifest.
