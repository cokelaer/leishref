# leishref Tasks & Roadmap

## Completed ✅

- [x] Init poetry package structure
- [x] Manifest CSV with 22-column schema
- [x] Aliases mapping (user-defined shortcuts)
- [x] Backfill existing files into manifest
- [x] NCBI fetch via datasets CLI (fasta+gff)
- [x] TriTrypDB fallback download (stub)
- [x] Ragtag scaffolding wrapper + AGP-based cleaning
- [x] Info command with provenance display
- [x] Add local files via `add` command
- [x] Untracked file warnings in `info`
- [x] Smart accession detection (GCA_/GCF_ prefixes)
- [x] Fetch confirmation (block duplicates, --force override)
- [x] GFF naming consistency with FASTA prefix
- [x] CLI refactored to single `leishref` group command
- [x] Project renamed: leishdb → leishref

## In Progress / High Priority 🚧

- [ ] **Version tracking** (separate from accession):
  - [ ] Populate `release_version` for NCBI (extract assembly version)
  - [ ] TriTrypDB: store as "tritrypdb-68" or similar
  - [ ] Add `version` column (user-facing) separate from DB release
  - [ ] `add` command accepts `--version` flag
  - [ ] Zenodo: track deposition version (v1.0, v2.0)

- [ ] **Download subcommand**:
  - [ ] Add `fasta_uri`, `gff_uri` columns to manifest
  - [ ] `leishref download <alias>` fetches from URIs
  - [ ] Support HTTP URLs + Zenodo DOI resolution
  - [ ] Auto-populate URIs when publishing to Zenodo
  - [ ] Verify checksums after download

- [ ] **Zenodo integration** (complete):
  - [ ] Implement actual deposition creation/upload (currently stub)
  - [ ] Auto-populate fasta_uri/gff_uri from Zenodo response
  - [ ] Update manifest.csv with DOI + URIs
  - [ ] Support re-uploading new versions (existing deposition ID tracking)

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

- pytest environment conflict with conda py311 (use `python3 -c` workaround)
- ragtag.py only in py311 env, not sequana_tools (auto-locate works)
- Zenodo publishing not yet functional (curl stubs only)

## Notes

- Git tracks: manifest.csv, aliases.csv, code, tests
- Git ignores: NCBI/*.fa*, Scaffold/*.fa*, MyAssemblies/**/*.fa*, *.pyc, pycache
- Schema evolving: `release_version` + `version` distinction pending
