# leishref Tasks & Roadmap

## Completed ✅

- [x] Init poetry package structure
- [x] Manifest CSV with 25-column schema (added num_bases, num_contigs, gc_percent)
- [x] Aliases mapping (user-defined shortcuts)
- [x] NCBI fetch via datasets CLI (fasta+gff) with GFF naming fix
- [x] TriTrypDB fallback download (stub, URLs prepared)
- [x] Ragtag scaffolding wrapper + AGP-based cleaning (chrom-anchored + kinetoplast whitelist)
- [x] Info command with provenance display (source, accession, release, DOI)
- [x] Add local files via `add` command (copies to MyAssemblies/, computes stats)
- [x] Untracked file warnings in `info`
- [x] Smart accession detection (GCA_/GCF_ prefixes)
- [x] Fetch confirmation (block duplicates, --force override, replace instead of append)
- [x] CLI refactored to single `leishref` group command
- [x] Project renamed: leishdb → leishref
- [x] **Zenodo publishing** (requests library, metadata update, sandbox vs production tokens)
- [x] Sandbox/production separation (DOIs only saved to manifest for production)
- [x] Genome statistics tracking (num_bases, num_contigs, gc_percent computed on fetch/add/scaffold)
- [x] Manifest update by filename for scaffolds (no accession fallback)
- [x] Rich-click CLI formatting (improved help text with better layout)
- [x] TriTrypDB fetch command (leishref fetch-tritrypdb <species_strain>)
- [x] **`verify` command** — re-hash files against manifest, non-zero exit on drift
- [x] **AGP derivation model** — `derived_from` + `agp_filename` columns, `leishref derive-agp`
- [x] `apply_agp()` reconstruction: child FASTA regenerable from parent + AGP
- [x] Path resolution for bare manifest filenames (`resolve_path`)
- [x] pytest runnable again (`-p no:asyncio`); AGP test suite added
- [x] **Catalog ships with the package** (`leishref/data/manifest.csv`), local manifest overlays it
- [x] **`download` command** — resolves Zenodo DOI or NCBI accession from the catalog, checks md5
- [x] `taxon_id` column, populated for all NCBI rows
- [x] Fixed `fetch_metadata`: parsed an obsolete datasets JSON shape, so assembly_name /
      bioproject / biosample / sequencing_technology were silently empty on every row

## In Progress / High Priority 🚧

- [ ] **Register TriTrypDB-68 as derivations** (login now required, so no auto-fetch):
  - [ ] `derive-agp --record` each local TriTrypDB genome against its NCBI parent
  - [ ] Map TriTrypDB genome -> NCBI accession (no explicit cross-reference in their FASTA)
  - [ ] **Compare GFFs**: TriTrypDB annotates in chromosome coords, NCBI in scaffold coords;
        lift over via the derived AGP, then measure real annotation differences
  - [ ] Speed: derivation is ~50 s per genome pair; ~69 genomes = ~1 h batch

- [ ] **`leishref diff A B`** — surface the derivation comparison without writing an AGP

- [ ] **`leishref materialize <alias>`** — rebuild a child FASTA from parent + AGP,
      so the repo is distributable without shipping third-party sequence

- [ ] **Version tracking** (for NCBI/TriTrypDB/Zenodo):
  - [ ] Populate `release_version` for NCBI (release_date is available from metadata)
  - [ ] TriTrypDB: store as "tritrypdb-68" or similar
  - [ ] Zenodo: use `--version` flag (v1.0, v2.0) → track in manifest

## Medium Priority 📋

- [ ] **Test suite**:
  - [ ] Integration tests for fetch/add/scaffold workflows
  - [ ] Mock NCBI datasets CLI responses
  - [ ] Mock Zenodo API for publish tests
  - [ ] End-to-end manifest consistency checks

- [ ] **Documentation**:
  - [ ] Workflow examples (fetch → scaffold → publish → download)
  - [ ] Troubleshooting guide
  - [ ] Manifest schema reference
  - [ ] Contributing guidelines

## Low Priority 💡

- [ ] Config file support (`.leishref.toml` for defaults)
- [ ] Parallel downloads (speed up bulk fetches)
- [ ] Database validation/repair commands
- [ ] Export manifest to different formats (JSON, YAML, TSV)
- [ ] Web UI / HTTP API for remote access
- [ ] Conda package distribution
- [ ] Docker image

## Known Issues 🐛

- ragtag.py only in py311 env, not sequana_tools (auto-locate works)

## Notes

- Git tracks: manifest.csv, aliases.csv, code, tests
- Git ignores: NCBI/*.fa*, Scaffold/*.fa*, MyAssemblies/**/*.fa*, *.pyc, pycache
- Schema evolving: `release_version` + `version` distinction pending
