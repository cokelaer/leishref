# leishref Tasks & Roadmap

## Completed

- [x] Poetry package, rich-click CLI
- [x] **One directory per genome** under `leishref/data/<id>/metadata.yaml`; the CSV
      manifest is gone, and with it the index-vs-truth sync problem
- [x] **User / developer split**: `leishref <cmd>` for using the database,
      `leishref dev <cmd>` for maintaining the catalog
- [x] Catalog ships with the package; local database at `data/<alias>/`
- [x] `download` resolves a Zenodo DOI or NCBI accession and verifies the md5
- [x] `--alias` compulsory on install; the directory name is the alias
- [x] `search` across the whole record (species, taxon, accession, provenance)
- [x] `verify`, non-zero exit on missing files or checksum drift
- [x] Alias-named relative symlinks (`link`, `--no-link`)
- [x] NCBI fetch via datasets CLI, with taxonomy and project metadata
- [x] Ragtag scaffolding with AGP-based cleaning (chrom-anchored plus kinetoplast)
- [x] Zenodo publishing, sandbox kept separate from production
- [x] AGP derivation and `apply_agp` reconstruction
- [x] Genome statistics at scaffold and contig level: num_scaffolds vs num_contigs,
      scaffold/contig N50 and L50, num_ungapped, num_ambiguous, num_gaps.
      Reproduces NCBI's assembly_stats exactly on all 13 NCBI entries
- [x] strain, assembly_level and release_date pulled from NCBI (strain lives in
      organism.infraspecific_names, not organism_name)
- [x] Suggested aliases on `download` and `info`
- [x] `dev add --technology/--assembler`; sequencing technology recorded for 15 of 17

## In Progress / High Priority 🚧

- [ ] **Register TriTrypDB-68 as derivations** (login now required, so no auto-fetch):
  - [ ] `dev derive-agp --record` each local TriTrypDB genome against its NCBI parent
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

- Git tracks: leishref/data/*/metadata.yaml (the catalog), AGP/*.agp, code, tests
- Git ignores: NCBI/*.fa*, Scaffold/*.fa*, MyAssemblies/**/*.fa*, *.pyc, pycache
- Schema evolving: `release_version` + `version` distinction pending
