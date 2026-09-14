# Leishmania Reference Genome Database (leishref)

Manage Leishmania genomes from NCBI, TriTrypDB, and custom assemblies with full provenance tracking, user-friendly aliasing, and automated ragtag scaffolding.

**Key features:**
- A curated catalog ships inside the package, so `pip install leishref` is the only
  entry point you need — no hunting across NCBI, TriTrypDB and Zenodo
- `leishref download <alias>` resolves whichever source a genome lives in and checks its md5
- User aliases for easy reference (e.g., `Ld1S` instead of full filename)
- Layouts recorded as derivations (parent assembly + AGP) rather than as separate genomes
- `verify` re-hashes everything on disk against the manifest
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
leishref --help
```

---

## Database Structure

```
Leishmania/
├── manifest.csv              # YOUR genomes (created on demand, overlays the catalog)
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
├── AGP/                      # Derived layouts (git-TRACKED — coordinates, not sequence)
│   └── TriTrypDB-68_LtropicaL590_Genome.agp
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
│   ├── agp.py                # AGP derivation, reconstruction
│   └── data/
│       └── manifest.csv      # THE CATALOG — ships with the package, PR-updated
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

## The catalog

`leishref/data/manifest.csv` ships inside the package. It is the curated index of every
genome leishref knows about: accession, checksums, statistics, Zenodo DOI, provenance.
It is updated by hand or by pull request, never written to at runtime.

Your own genomes go in a `manifest.csv` in the working directory, created the first time
you run `add`, `fetch` or `scaffold`. It overlays the catalog: a local row replaces the
catalog row with the same filename, so you can correct or extend the shipped index
without editing it.

```console
$ leishref info
18 genomes: 17 from catalog, 1 local
  catalog: .../leishref/data/manifest.csv
  local:   manifest.csv

my_assembly.fa  [local]
  alias: MyStrain
  ...
```

`--manifest <path>` bypasses both and uses that one file.

### Getting the sequence

The catalog records where each genome actually lives, so one command fetches it:

```bash
leishref download Ld1S                 # by alias
leishref download GCA_000410715.1      # by accession
leishref download Ltropica.Ld1S.scaffold.flye.fasta   # by filename
```

It prefers a Zenodo DOI when the catalog has one and falls back to the NCBI accession,
then checks the downloaded file against the recorded md5:

```console
$ leishref download Ltropica.Ld1S.scaffold.pecat.fasta
Ltropica.Ld1S.scaffold.pecat.fasta -> 10.5281/zenodo.22710148 (Zenodo)
  MyAssemblies/Ltropica.Ld1S.scaffold.pecat.fasta
  MyAssemblies/Ltropica.Ld1S.scaffold.pecat.agp
  md5 OK: Ltropica.Ld1S.scaffold.pecat.fasta
```

Zenodo downloads need no token. TriTrypDB genomes have neither a DOI nor an accession,
so `download` points you at `add` instead.

### Contributing a genome

1. `leishref fetch <accession>` (or `add`) — lands in your local `manifest.csv`
2. Move the row into `leishref/data/manifest.csv`
3. Open a PR

---

## Manifest Schema

Single CSV with 28 columns, one row per genome/scaffold:

| Column | Type | Description |
|--------|------|-------------|
| `filename` | str | Fasta filename (relative path) |
| `gff_filename` | str | GFF filename (relative path, may be empty) |
| `source` | str | NCBI, TriTrypDB, MyAssembly, Scaffold |
| `accession` | str | NCBI/TriTrypDB accession (e.g., GCA_000410715.1) |
| `assembly_name` | str | Full assembly name from NCBI |
| `release_version` | str | Release/version tag |
| `taxon_id` | int | NCBI taxonomy id (5661 = *L. donovani*, 5666 = *L. tropica*, ...) |
| `species` | str | Genus species (e.g., Leishmania_major) |
| `strain` | str | Strain name (e.g., Friedlin) |
| `alias` | str | User alias for easy lookup |
| `md5sum_fasta` | str | Checksum of fasta file |
| `md5sum_gff` | str | Checksum of GFF file |
| `scaffold_reference_alias` | str | Alias of reference used for scaffolding |
| `scaffold_tool_version` | str | ragtag.py version |
| `cleaned` | bool | True if pruned to chr-anchored + kinetoplast |
| `cleaned_from` | str | Filename of original (unclean) scaffold |
| `derived_from` | str | Parent assembly this is a re-layout of (see Derivation model) |
| `agp_filename` | str | AGP describing the layout relative to `derived_from` |
| `zenodo_doi` | str | Zenodo deposition DOI (if published) |
| `sequencing_technology` | str | Sequencing method from NCBI metadata |
| `bioproject` | str | NCBI BioProject accession |
| `biosample` | str | NCBI BioSample accession |
| `raw_reads_accession` | str | SRA accession for raw reads |
| `date_added` | str | ISO date added to DB |
| `notes` | str | Free-text notes (e.g., "added locally", "length differs from <other>") |

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

### 1. Fetch a genome from NCBI

Downloads fasta + GFF from NCBI using `datasets` CLI; extracts metadata (sequencing tech, BioProject, BioSample); appends manifest row.

```bash
# Fetch *L. tropica* L590 from NCBI (accession is positional)
leishref fetch GCA_000410715.1 \
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

### 2. Scaffold a query against a reference

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

### 3. Publish a scaffold to Zenodo

Create a Zenodo deposition for a single scaffold (fasta + AGP), upload, publish, and get DOI.

**Setup (one-time):**
1. Get API token from https://zenodo.org/account/settings/applications/tokens/new (or sandbox.zenodo.org for testing)
2. Set environment variable:
   - **Bash/Zsh:** `export ZENODO_TOKEN="your-token"`
   - **Fish:** `set -x ZENODO_TOKEN your-token` (note: `-x` to export)
3. For sandbox testing: `ZENODO_SANDBOX_TOKEN` (separate token from sandbox.zenodo.org)

**Usage:**
```bash
# Dry-run (preview, no token needed)
leishref publish Scaffold/Ltropica.CDC.onLd1S.fa

# Publish to sandbox for testing
leishref publish Scaffold/Ltropica.CDC.onLd1S.fa --sandbox --confirm

# Publish to production
leishref publish Scaffold/Ltropica.CDC.onLd1S.fa --version v1.0 --confirm
```

Result:
- Deposition created on Zenodo with title + metadata
- Files uploaded (`.fa` + `.agp`)
- Published (made public) with DOI
- DOI written to manifest.csv `zenodo_doi` column
- Version tracked if `--version` provided

### 4. Look up in manifest

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

## Derivation model

Contig counts differ wildly between sources for the same organism. For *L. tropica* L590:

| source | sequences |
|---|---|
| NCBI `GCA_000410715.1` | 448 (182 scaffolds + 266 WGS contigs) |
| TriTrypDB-68 | 160 (36 chromosomes + 124 supercontigs) |
| ragtag on Ld1S | 140 |

These are **not three genomes**. They are one sequence with three chromosome
assignments. Measured on the NCBI/TriTrypDB pair: non-N content differs by 324 bases
in 31.3 Mb (0.001%), and every large NCBI scaffold appears inside the TriTrypDB
assembly — about half of them reverse-complemented, joined with 100-N padding.

So leishref records a layout as a **derivation**, not as a new genome:

- `derived_from` — the parent assembly supplying the sequence
- `agp_filename` — an AGP giving order, orientation and gaps relative to that parent

Two consequences:

1. **Choosing what to use** becomes an explicit choice of layout over one lineage,
   not a guess about which FASTA is "better".
2. **Third-party sequence never needs redistributing.** An AGP is coordinates —
   a few hundred KB of facts. `leishref derive-agp` produces one; `apply_agp()`
   regenerates the child FASTA from parent + AGP. Zenodo depositions therefore
   only ever carry your own assemblies, your AGPs, and the manifest.

```bash
leishref derive-agp \
  NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna \
  TriTryDB68/TriTrypDB-68_LtropicaL590_Genome.fasta \
  --record

#   parent sequences:  448 (441 placed)
#   child sequences:   160 (158 used)
#   blocks placed:     1894/1938
#   orientation:       969 forward, 925 reverse
#   coverage:          97.556% of non-N parent bases
#   Same sequence, different layout: child is a re-scaffolding of parent.
```

Coverage below ~95% means the two really are different assemblies, not a re-layout.

The residual on this pair (2.4% N from unplaced blocks, 0.026% true mismatch on
round-trip) is TriTrypDB's own sequence editing — visible precisely *because* the
layout is now explicit.

### TriTrypDB access

TriTrypDB downloads now require a login, so `leishref fetch-tritrypdb` cannot fetch
unattended. Download the release by hand, then register each genome as a derivation
of its NCBI parent with `derive-agp --record`. Their GFF is in chromosome
coordinates and NCBI's is in scaffold coordinates; the same AGP is what relates them.

---

## Integrity checking

```bash
leishref verify           # re-hash every file, compare against the manifest
leishref verify --quick   # presence only, skip checksums
```

Reports missing files and checksum mismatches, and exits non-zero if either is
found, so it can gate CI or run from cron.

---

## Workflow Examples

### Add a known NCBI genome + scaffold onto Ld1S reference

```bash
# 1. Fetch from NCBI
leishref fetch GCA_000410715.1 --alias Ltropica.L590

# 2. Scaffold onto Ld1S (assumes Ld1S alias exists and points to NCBI/Ld1S.fa)
leishref scaffold \
  --query NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna \
  --reference Ld1S \
  --clean \
  --alias Ltropica.L590.onLd1S

# 3. Publish scaffold to Zenodo
export ZENODO_TOKEN="..."
leishref publish Scaffold/Ltropica.L590.onLd1S.fa --confirm

# 4. View manifest
leishref info
```

### Register a custom assembly + scaffold it

```bash
# 1. Add it (copies into MyAssemblies/, computes md5 and stats)
leishref add ~/my_assembly.fasta --species Leishmania_major --strain MyStrain --alias MyStrain

# 2. Scaffold onto reference
leishref scaffold --query MyAssemblies/my_assembly.fasta --reference Ld1S --clean --alias MyStrain.onLd1S

# 3. Confirm nothing drifted
leishref verify
```

---

## Development

### Run tests

```bash
poetry run pytest
poetry run pytest --cov=leishref --cov-report=term-missing
poetry run pytest tests/test_agp.py::test_agp_roundtrip_reconstructs_child -xvs
```

`pytest-asyncio` in the ambient conda env is incompatible with this pytest and breaks
collection; `addopts = "-p no:asyncio"` in `pyproject.toml` disables it.

### Lint & format

```bash
# Per CLAUDE.md defaults
black --line-length=120 leishref/ tests/
isort --profile=black leishref/ tests/
flake8 leishref/ tests/
```

### Add a new source

Add a module (e.g. `leishref/newsource.py`) exposing a download function, then wire a subcommand in `leishref/cli.py`.

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
