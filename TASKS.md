# leishref Tasks & Roadmap

## Completed ✅

- [x] Init poetry package structure
- [x] Manifest CSV with 25-column schema (added num_bases, num_contigs, gc_percent)
- [x] Aliases mapping (user-defined shortcuts)
- [x] Backfill existing files into manifest
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

## In Progress / High Priority 🚧

- [ ] **Download subcommand** (fetch genomes from manifest URIs):
  - [ ] Add `fasta_uri`, `gff_uri` columns to manifest
  - [ ] `leishref download <alias>` fetches from URIs
  - [ ] Support HTTP URLs + Zenodo DOI resolution
  - [ ] Auto-populate URIs when publishing to Zenodo
  - [ ] Verify checksums after download

- [ ] **Version tracking** (for NCBI/TriTrypDB/Zenodo):
  - [ ] Populate `release_version` for NCBI (extract from assembly_name)
  - [ ] TriTrypDB: store as "tritrypdb-68" or similar
  - [ ] Zenodo: use `--version` flag (v1.0, v2.0) → track in manifest

## Medium Priority 📋

- [ ] **TriTrypDB proper support**:
  - [ ] Implement actual download (currently stub URL pattern)
  - [ ] Extract version/release from TriTrypDB metadata
  - [ ] Length comparison vs NCBI (currently noted only)

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

- pytest environment conflict with conda py311: use `poetry run pytest` instead
- ragtag.py only in py311 env, not sequana_tools (auto-locate works)

## Notes

- Git tracks: manifest.csv, aliases.csv, code, tests
- Git ignores: NCBI/*.fa*, Scaffold/*.fa*, MyAssemblies/**/*.fa*, *.pyc, pycache
- Schema evolving: `release_version` + `version` distinction pending
