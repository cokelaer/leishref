"""CLI entry points for leishref."""

import shutil
import tempfile
from pathlib import Path

import rich_click as click

from leishref.agp import derive_agp, write_agp
from leishref.checksums import contig_count, gc_percent, md5_file, sequence_length
from leishref.manifest import DATA_DIRS, Catalog, ManifestRow, resolve_path, today_iso
from leishref.ncbi import fetch_fasta_gff, fetch_metadata
from leishref.scaffold import clean_scaffolded_fasta, run_scaffold
from leishref.tritrypdb import download_fasta_gff as tritrypdb_download
from leishref.zenodo import (
    ZenodoError,
    create_deposition,
    download_record_files,
    is_sandbox_doi,
    publish_deposition,
    record_id_from_doi,
    update_metadata,
    upload_file,
)


@click.group()
def cli():
    """Leishmania reference genome database."""
    pass


def _catalog(manifest) -> Catalog:
    """An explicit --manifest means that one file; otherwise catalog + local overlay."""
    if manifest:
        return Catalog(local=manifest, catalog=manifest)
    return Catalog()


@cli.command()
@click.argument("accession")
@click.option("--species", help="Species name (inferred from NCBI if not given)")
@click.option("--strain", help="Strain name (inferred from NCBI if not given)")
@click.option("--alias", help="Short alias for this genome")
@click.option("--outdir", type=click.Path(), default="NCBI", help="Output directory")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--force", is_flag=True, help="Re-fetch even if already in manifest")
def fetch(accession, species, strain, alias, outdir, manifest, force):
    """Fetch genome from NCBI. Detects GCA_/GCF_ accessions automatically.

    Examples:
      leishref fetch GCA_000410715.1
      leishref fetch GCA_000410715.1 --alias Ld1S
      leishref fetch GCA_000410715.1 --force
    """
    outdir = Path(outdir)
    catalog = _catalog(manifest)

    # Detect if it looks like an NCBI accession
    is_accession = accession.upper().startswith(("GCA_", "GCF_"))
    if is_accession:
        click.echo(f"Detected NCBI accession: {accession}")

    # Check if already in manifest
    existing = catalog.find_by_accession(accession)
    if existing and not force:
        click.echo(f"Already in manifest: {existing.get('filename')}", err=True)
        click.echo(f"Use --force to re-fetch", err=True)
        return

    if existing and force:
        click.echo(f"Re-fetching (--force): {accession}")

    click.echo(f"Fetching {accession} from NCBI...")
    fasta, gff = fetch_fasta_gff(accession, outdir)
    if not fasta:
        click.echo(f"Not found on NCBI: {accession}", err=True)
        return

    md5_fasta = md5_file(fasta)
    md5_gff = md5_file(gff) if gff else None

    meta = fetch_metadata(accession)
    # organism_name is "Genus species strain..."; assembly_name is not a species name.
    organism = (meta.get("organism_name") or "").split()

    row = ManifestRow(
        filename=fasta.name,
        gff_filename=gff.name if gff else None,
        source="NCBI",
        accession=accession,
        assembly_name=meta.get("assembly_name"),
        release_version=None,
        taxon_id=meta.get("taxon_id"),
        species=species or (" ".join(organism[:2]) if len(organism) >= 2 else None),
        strain=strain or (" ".join(organism[2:]) or None),
        alias=alias,
        md5sum_fasta=md5_fasta,
        md5sum_gff=md5_gff,
        num_bases=sequence_length(fasta),
        num_contigs=contig_count(fasta),
        gc_percent=gc_percent(fasta),
        date_added=today_iso(),
        sequencing_technology=meta.get("sequencing_technology"),
        bioproject=meta.get("bioproject"),
        biosample=meta.get("biosample"),
        notes=None,
    )

    catalog.upsert_local(row)
    click.echo(f"{'Updated' if force else 'Added'} {accession} in {catalog.local_path}")


@cli.command()
@click.argument("fasta", type=click.Path(exists=True))
@click.argument("gff", type=click.Path(exists=True), required=False)
@click.option("--species", help="Species name")
@click.option("--strain", help="Strain name")
@click.option("--alias", help="Short alias")
@click.option("--outdir", type=click.Path(), default="MyAssemblies", help="Destination directory")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
def add(fasta, gff, species, strain, alias, outdir, manifest):
    """Add local fasta/gff files to database and manifest.

    Examples:
      leishref add /path/to/assembly.fa --species Leishmania_major --strain myStrain
      leishref add assembly.fa assembly.gff --alias MyGenome
    """
    fasta = Path(fasta)
    gff = Path(gff) if gff else None
    outdir = Path(outdir)
    catalog = _catalog(manifest)

    outdir.mkdir(parents=True, exist_ok=True)

    # Copy files
    new_fasta = outdir / fasta.name
    new_fasta.write_bytes(fasta.read_bytes())
    click.echo(f"Copied {fasta.name} → {new_fasta}")

    new_gff = None
    if gff:
        new_gff = outdir / gff.name
        new_gff.write_bytes(gff.read_bytes())
        click.echo(f"Copied {gff.name} → {new_gff}")

    # Add to manifest
    md5_fa = md5_file(new_fasta)
    md5_gf = md5_file(new_gff) if new_gff else None

    row = ManifestRow(
        filename=new_fasta.name,
        gff_filename=new_gff.name if new_gff else None,
        source="MyAssembly",
        species=species,
        strain=strain,
        alias=alias,
        md5sum_fasta=md5_fa,
        md5sum_gff=md5_gf,
        num_bases=sequence_length(new_fasta),
        num_contigs=contig_count(new_fasta),
        gc_percent=gc_percent(new_fasta),
        date_added=today_iso(),
        notes="added locally",
    )

    catalog.upsert_local(row)
    click.echo(f"Added to manifest: {new_fasta.name}")


@cli.command()
@click.option("--query", type=click.Path(exists=True), required=True, help="Query fasta file")
@click.option("--reference", required=True, help="Reference alias or filename")
@click.option("--outdir", type=click.Path(), default="Scaffold", help="Output directory")
@click.option("--alias", help="Alias for this scaffold")
@click.option("--clean", is_flag=True, help="Keep only chr-anchored contigs + kinetoplast")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--ragtag-bin", help="Path to ragtag.py (auto-detect if not given)")
def scaffold(query, reference, outdir, alias, clean, manifest, ragtag_bin):
    """Run ragtag scaffold on query against reference.

    Examples:
      leishref scaffold --query assembly.fa --reference Ld1S
      leishref scaffold --query assembly.fa --reference Ld1S --alias MyScaffold --clean
    """
    query = Path(query)
    outdir = Path(outdir)
    catalog = _catalog(manifest)

    ref_row = catalog.find_by_alias(reference)
    if not ref_row or not ref_row.get("filename"):
        click.echo(f"Reference {reference} not found in manifest", err=True)
        return

    ref_path = Path(ref_row["filename"])
    if not ref_path.exists():
        ref_path = Path("NCBI") / ref_path
    if not ref_path.exists():
        click.echo(f"Reference file not found: {ref_path}", err=True)
        return

    click.echo(f"Scaffolding {query.name} onto {reference}...")
    outdir.mkdir(parents=True, exist_ok=True)

    tmp_outdir = Path(tempfile.mkdtemp())
    try:
        scaffold_fasta, scaffold_agp = run_scaffold(ref_path, query, tmp_outdir)

        species_strain = query.stem.split(".")[0]
        prefix = f"{species_strain}.on.{alias or reference}"
        out_fasta = outdir / f"{prefix}.fa"
        out_agp = outdir / f"{prefix}.agp"

        shutil.copy(scaffold_fasta, out_fasta)
        shutil.copy(scaffold_agp, out_agp)

        if clean:
            cleaned_content = clean_scaffolded_fasta(scaffold_fasta, scaffold_agp)
            cleaned_fasta = outdir / f"{prefix}.cleaned.fa"
            cleaned_fasta.write_text(cleaned_content)

            md5_cleaned = md5_file(cleaned_fasta)
            row_cleaned = ManifestRow(
                filename=cleaned_fasta.name,
                source="Scaffold",
                scaffold_reference_alias=reference,
                scaffold_tool_version="ragtag.py",
                cleaned=True,
                cleaned_from=out_fasta.name,
                md5sum_fasta=md5_cleaned,
                num_bases=sequence_length(cleaned_fasta),
                num_contigs=contig_count(cleaned_fasta),
                gc_percent=gc_percent(cleaned_fasta),
                date_added=today_iso(),
                alias=alias,
            )
            catalog.upsert_local(row_cleaned)
            click.echo(f"Scaffold (cleaned): {cleaned_fasta.name}")
        else:
            md5_scaffold = md5_file(out_fasta)
            row = ManifestRow(
                filename=out_fasta.name,
                source="Scaffold",
                scaffold_reference_alias=reference,
                scaffold_tool_version="ragtag.py",
                cleaned=False,
                md5sum_fasta=md5_scaffold,
                num_bases=sequence_length(out_fasta),
                num_contigs=contig_count(out_fasta),
                gc_percent=gc_percent(out_fasta),
                date_added=today_iso(),
                alias=alias,
            )
            catalog.upsert_local(row)
            click.echo(f"Scaffold: {out_fasta.name}")

    finally:
        import shutil as sh

        sh.rmtree(tmp_outdir, ignore_errors=True)


@cli.command("fetch-tritrypdb")
@click.argument("species_strain")
@click.option("--outdir", type=click.Path(), default="TriTryDB68", help="Output directory")
@click.option("--species", help="Species name (inferred if not given)")
@click.option("--strain", help="Strain name (inferred if not given)")
@click.option("--alias", help="Short alias for this genome")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
def fetch_tritrypdb(species_strain, outdir, species, strain, alias, manifest):
    """Fetch genome from TriTrypDB release 68.

    Examples:
      leishref fetch-tritrypdb Leishmania_major_Friedlin
      leishref fetch-tritrypdb Leishmania_infantum_JPCM5 --alias Linf
    """
    outdir = Path(outdir)
    catalog = _catalog(manifest)

    click.echo(f"Fetching {species_strain} from TriTrypDB...")
    fasta, gff = tritrypdb_download(species_strain, outdir)

    if not fasta:
        click.echo(f"Not found on TriTrypDB: {species_strain}", err=True)
        return

    md5_fasta = md5_file(fasta)
    md5_gff = md5_file(gff) if gff else None

    row = ManifestRow(
        filename=fasta.name,
        gff_filename=gff.name if gff else None,
        source="TriTrypDB",
        release_version="68",
        species=species or species_strain.split("_")[0],
        strain=strain or "_".join(species_strain.split("_")[1:]),
        alias=alias,
        md5sum_fasta=md5_fasta,
        md5sum_gff=md5_gff,
        num_bases=sequence_length(fasta),
        num_contigs=contig_count(fasta),
        gc_percent=gc_percent(fasta),
        date_added=today_iso(),
        notes="fetched from TriTrypDB release 68",
    )

    catalog.upsert_local(row)
    click.echo(f"Added {species_strain} to manifest: {fasta.name}")


@cli.command()
@click.argument("scaffold", type=click.Path(exists=True))
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--version", help="Version tag (e.g., v1.0)")
@click.option("--confirm", is_flag=True, help="Actually publish (else dry-run)")
@click.option("--sandbox", is_flag=True, help="Publish to sandbox.zenodo.org (test)")
def publish(scaffold, manifest, version, confirm, sandbox):
    """Publish scaffold (fasta+agp) to Zenodo. Requires ZENODO_TOKEN env var.

    Examples:
      leishref publish scaffold.fa --confirm
      leishref publish scaffold.fa --sandbox --confirm
      leishref publish scaffold.fa --version v1.0 --confirm
    """
    scaffold = Path(scaffold)
    catalog = _catalog(manifest)

    # Find corresponding AGP file
    agp_file = scaffold.with_suffix(".agp")
    if not agp_file.exists():
        click.echo(f"AGP file not found: {agp_file}", err=True)
        return

    # Check if already published
    row = catalog.find_by_filename(scaffold.name)
    if row and row.get("zenodo_doi"):
        click.echo(f"Already published with DOI: {row.get('zenodo_doi')}", err=True)
        click.echo("(To publish a new version, use a new filename)", err=True)
        return

    if not confirm:
        click.echo(f"Dry-run: would publish {scaffold.name} + {agp_file.name} to Zenodo")
        click.echo(f"Add --confirm to actually publish")
        return

    try:
        click.echo("Creating Zenodo deposition...")
        title = f"Leishmania scaffold: {scaffold.stem}"
        description = f"Ragtag-scaffolded genome assembly for {scaffold.stem}"
        creators = ["Leishmania Database"]

        dep = create_deposition(title, description, creators, sandbox=sandbox)
        dep_id = dep["id"]
        click.echo(f"Created deposition {dep_id}")

        click.echo(f"Uploading {scaffold.name}...")
        upload_file(dep_id, scaffold, sandbox=sandbox)

        click.echo(f"Uploading {agp_file.name}...")
        upload_file(dep_id, agp_file, sandbox=sandbox)

        # Update metadata with version + keywords (preserve existing title/creators)
        meta = {
            "metadata": {
                "title": dep["metadata"]["title"],
                "creators": dep["metadata"]["creators"],
                "version": version or "v1.0",
                "keywords": ["leishmania", "scaffold", "ragtag", "genome"],
                "upload_type": "dataset",
            }
        }
        update_metadata(dep_id, meta, sandbox=sandbox)
        click.echo(f"Updated metadata with version {version or 'v1.0'}")

        click.echo("Publishing...")
        published = publish_deposition(dep_id, sandbox=sandbox)

        doi = published.get("doi") or published.get("conceptdoi")
        click.echo(f"Published! DOI: {doi}")

        # Sandbox DOIs are throwaway; recording one would block the real publish.
        if sandbox:
            click.echo("Sandbox publish (manifest not updated)")
        else:
            updated = (
                ManifestRow(**{k: v for k, v in row.items() if k != "_origin"})
                if row
                else ManifestRow(
                    filename=scaffold.name,
                    gff_filename=agp_file.name,
                    source="Scaffold",
                    date_added=today_iso(),
                )
            )
            updated["zenodo_doi"] = doi
            updated["release_version"] = version or updated.get("release_version")
            catalog.upsert_local(updated)
            click.echo(f"Recorded DOI in {catalog.local_path}")

    except ZenodoError as e:
        click.echo(f"Zenodo error: {e}", err=True)
        return


@cli.command()
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--basedir", type=click.Path(), default=".", help="Root to resolve filenames against")
@click.option("--quick", is_flag=True, help="Check presence only, skip checksums")
def verify(manifest, basedir, quick):
    """Check that files on disk still match the manifest.

    Examples:
      leishref verify
      leishref verify --quick
    """
    catalog = _catalog(manifest)
    rows = catalog.read()
    basedir = Path(basedir)

    missing, mismatch, ok = [], [], 0

    for row in rows:
        for kind, name_col, md5_col in (
            ("fasta", "filename", "md5sum_fasta"),
            ("gff", "gff_filename", "md5sum_gff"),
        ):
            name = row.get(name_col)
            if not name:
                continue
            path = resolve_path(name, basedir)
            if path is None:
                missing.append((name, kind))
                continue
            recorded = row.get(md5_col)
            if quick or not recorded:
                ok += 1
                continue
            if md5_file(path) != recorded:
                mismatch.append((name, kind, path))
            else:
                ok += 1

    click.echo(f"Checked {len(rows)} manifest rows")
    click.echo(f"  ok:       {ok}")
    click.echo(f"  missing:  {len(missing)}")
    click.echo(f"  mismatch: {len(mismatch)}")

    if missing:
        click.echo("\nMISSING (in manifest, not on disk):", err=True)
        for name, kind in missing:
            click.echo(f"  {name}  [{kind}]", err=True)

    if mismatch:
        click.echo("\nCHECKSUM MISMATCH (file changed since it was recorded):", err=True)
        for name, kind, path in mismatch:
            click.echo(f"  {path}  [{kind}]", err=True)

    if missing or mismatch:
        raise SystemExit(1)


@cli.command("derive-agp")
@click.argument("parent", type=click.Path())
@click.argument("child", type=click.Path())
@click.option("--out", type=click.Path(), help="AGP output path (default AGP/<child stem>.agp)")
@click.option("--basedir", type=click.Path(), default=".", help="Root to resolve filenames against")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--record", is_flag=True, help="Write derived_from + agp_filename to the child's manifest row")
@click.option("--probe-len", default=60, show_default=True, help="Anchor length used to locate blocks")
def derive_agp_cmd(parent, child, out, basedir, manifest, record, probe_len):
    """Derive an AGP showing how CHILD was laid out from PARENT sequences.

    Reconstructs the layout (order, orientation, gaps) of a re-scaffolded assembly
    relative to its source. Lets a third-party layout be stored as coordinates
    instead of redistributed sequence.

    Examples:
      leishref derive-agp NCBI/GCA_000410715.1_..._genomic.fna TriTryDB68/TriTrypDB-68_LtropicaL590_Genome.fasta
      leishref derive-agp parent.fna child.fasta --record
    """
    basedir = Path(basedir)
    parent_path = resolve_path(parent, basedir) or Path(parent)
    child_path = resolve_path(child, basedir) or Path(child)

    for label, path in (("parent", parent_path), ("child", child_path)):
        if not path.exists():
            click.echo(f"{label} not found: {path}", err=True)
            raise SystemExit(1)

    click.echo(f"parent: {parent_path}")
    click.echo(f"child:  {child_path}")
    click.echo("Deriving layout (this scans both assemblies)...")

    lines, stats = derive_agp(parent_path, child_path, probe_len=probe_len)

    out_path = Path(out) if out else basedir / "AGP" / f"{child_path.stem}.agp"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_agp(out_path, lines)

    click.echo("")
    click.echo(f"  parent sequences:  {stats['parent_sequences']} ({stats['parent_sequences_placed']} placed)")
    click.echo(f"  child sequences:   {stats['child_sequences']} ({stats['child_sequences_used']} used)")
    click.echo(f"  blocks placed:     {stats['blocks_placed']}/{stats['blocks_total']}")
    click.echo(f"  orientation:       {stats['forward']} forward, {stats['reverse']} reverse")
    click.echo(f"  coverage:          {stats['coverage_of_non_n_parent']}% of non-N parent bases")
    if stats["blocks_unplaced"]:
        click.echo(f"  unplaced:          {stats['blocks_unplaced']} blocks, {stats['unplaced_bases']:,} bases")
    click.echo(f"\nWrote {out_path} ({len(lines)} lines)")

    if stats["coverage_of_non_n_parent"] >= 95:
        click.echo("Same sequence, different layout: child is a re-scaffolding of parent.")
    else:
        click.echo("Low coverage: these are likely genuinely different assemblies.")

    if record:
        catalog = _catalog(manifest)
        target = catalog.find_by_filename(child_path.name)
        if target is None:
            click.echo(f"No manifest row for {child_path.name}; add it first", err=True)
            raise SystemExit(1)
        updated = ManifestRow(**{k: v for k, v in target.items() if k != "_origin"})
        updated["derived_from"] = parent_path.name
        updated["agp_filename"] = out_path.name
        catalog.upsert_local(updated)
        click.echo(f"Recorded derived_from={parent_path.name} agp_filename={out_path.name}")


@cli.command()
@click.argument("name")
@click.option("--outdir", type=click.Path(), help="Destination (defaults to the source's usual directory)")
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--force", is_flag=True, help="Download even if the file is already present")
def download(name, outdir, manifest, force):
    """Fetch a genome named in the catalog, by alias, filename or accession.

    Resolves whichever source the catalog records -- a Zenodo DOI if the genome was
    published there, otherwise the NCBI accession -- so callers do not need to know
    where a given genome lives.

    Examples:
      leishref download Ld1S
      leishref download GCA_000410715.1
      leishref download Ltropica.Ld1S.scaffold.flye.fasta
    """
    catalog = _catalog(manifest)
    row = catalog.resolve(name)
    if row is None:
        click.echo(f"Not in catalog: {name}", err=True)
        click.echo("Run 'leishref info' to list what is available", err=True)
        raise SystemExit(1)

    filename = row.get("filename")
    doi = row.get("zenodo_doi")
    accession = row.get("accession")
    source = row.get("source") or "?"

    existing = resolve_path(filename) if filename else None
    if existing and not force:
        click.echo(f"Already present: {existing}")
        click.echo("Use --force to download again")
        return

    if doi:
        dest = Path(outdir) if outdir else Path("Scaffold" if source == "Scaffold" else "MyAssemblies")
        click.echo(f"{name} -> {doi} (Zenodo)")
        written = download_record_files(record_id_from_doi(doi), dest, sandbox=is_sandbox_doi(doi))
    elif accession:
        dest = Path(outdir) if outdir else Path("NCBI")
        click.echo(f"{name} -> {accession} (NCBI)")
        fasta, gff = fetch_fasta_gff(accession, dest)
        if not fasta:
            click.echo(f"NCBI has no data for {accession}", err=True)
            raise SystemExit(1)
        written = [p for p in (fasta, gff) if p]
    else:
        click.echo(f"{name} has no Zenodo DOI or NCBI accession in the catalog", err=True)
        if source == "TriTrypDB":
            click.echo("TriTrypDB requires a login; download by hand, then 'leishref add'", err=True)
        raise SystemExit(1)

    for path in written:
        click.echo(f"  {path}")

    recorded = {row.get("filename"): row.get("md5sum_fasta"), row.get("gff_filename"): row.get("md5sum_gff")}
    bad = False
    for path in written:
        want = recorded.get(path.name)
        if not want:
            continue
        if md5_file(path) == want:
            click.echo(f"  md5 OK: {path.name}")
        else:
            click.echo(f"  md5 MISMATCH: {path.name}", err=True)
            bad = True
    if bad:
        raise SystemExit(1)


@cli.command()
@click.option("--manifest", type=click.Path(), help="Use this manifest alone, instead of catalog + ./manifest.csv")
@click.option("--alias", help="Look up specific alias")
def info(manifest, alias):
    """Display manifest info with provenance. Warn about untracked files."""
    catalog = _catalog(manifest)
    rows = catalog.read()

    if alias:
        row = catalog.resolve(alias)
        if row:
            for k, v in row.items():
                if k == "_origin":
                    continue
                click.echo(f"{k}: {v}")
        else:
            click.echo(f"Alias not found: {alias}", err=True)
    else:
        n_catalog, n_local = catalog.counts()
        click.echo(f"{len(rows)} genomes: {n_catalog} from catalog, {n_local} local")
        click.echo(f"  catalog: {catalog.catalog_path}")
        click.echo(f"  local:   {catalog.local_path}" + ("" if catalog.local_path.exists() else " (not created yet)"))
        click.echo()
        for row in rows:
            filename = row.get("filename", "N/A")
            alias_name = row.get("alias") or "(no alias)"
            source = row.get("source", "?")
            accession = row.get("accession") or ""
            zenodo = row.get("zenodo_doi") or ""
            release_ver = row.get("release_version") or ""
            local_mark = "  [local]" if row.get("_origin") == "local" else ""

            click.echo(f"{filename}{local_mark}")
            click.echo(f"  alias: {alias_name}")
            click.echo(f"  source: {source}", nl=False)
            if accession:
                click.echo(f" | accession: {accession}", nl=False)
            if release_ver:
                click.echo(f" | release: {release_ver}", nl=False)
            click.echo("")
            if zenodo:
                click.echo(f"  zenodo_doi: {zenodo}")
            click.echo()

        # Check for untracked files
        tracked_files = {row.get("filename") for row in rows if row.get("filename")}
        untracked = []
        for datadir in DATA_DIRS:
            dirpath = Path(datadir)
            if dirpath.exists():
                for fpath in dirpath.rglob("*.fa*"):
                    if fpath.suffix not in [".fai"]:
                        if fpath.name not in tracked_files:
                            untracked.append(fpath)

        if untracked:
            click.echo("⚠️  UNTRACKED FILES (not in manifest):")
            for fpath in untracked:
                click.echo(f"  {fpath}", err=True)
            click.echo(f"Use 'leishref add <file>' to track them", err=True)
            click.echo()


if __name__ == "__main__":
    cli()
