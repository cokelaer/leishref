"""CLI entry points for leishref."""

import shutil
import tempfile
from pathlib import Path

import click

from leishref.aliases import Aliases
from leishref.checksums import contig_count, gc_percent, md5_file, sequence_length
from leishref.manifest import Manifest, ManifestRow
from leishref.ncbi import fetch_fasta_gff, fetch_metadata
from leishref.scaffold import clean_scaffolded_fasta, parse_agp, run_scaffold
from leishref.tritrypdb import download_fasta_gff as tritrypdb_download
from leishref.zenodo import create_deposition, upload_file, update_metadata, publish_deposition, ZenodoError


@click.group()
def cli():
    """Leishmania reference genome database."""
    pass


@cli.command()
@click.argument("accession")
@click.option("--species", help="Species name (inferred from NCBI if not given)")
@click.option("--strain", help="Strain name (inferred from NCBI if not given)")
@click.option("--alias", help="Short alias for this genome")
@click.option("--outdir", type=click.Path(), default="NCBI", help="Output directory")
@click.option("--manifest", type=click.Path(), default="manifest.csv", help="Manifest CSV")
@click.option("--force", is_flag=True, help="Re-fetch even if already in manifest")
def fetch(accession, species, strain, alias, outdir, manifest, force):
    """Fetch genome from NCBI. Detects GCA_/GCF_ accessions automatically.

    Usage:
      leishref fetch GCA_000410715.1
      leishref fetch GCA_000410715.1 --alias Ld1S
      leishref fetch GCA_000410715.1 --force  # re-fetch if exists
    """
    outdir = Path(outdir)
    manifest_obj = Manifest(Path(manifest))

    # Detect if it looks like an NCBI accession
    is_accession = accession.upper().startswith(("GCA_", "GCF_"))
    if is_accession:
        click.echo(f"Detected NCBI accession: {accession}")

    # Check if already in manifest
    existing = manifest_obj.find_by_accession(accession)
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
    assembly_name = meta.get("assembly_name", "")
    seq_tech = meta.get("sequencing_technology")
    bioproject = meta.get("bioproject")
    biosample = meta.get("biosample")

    row = ManifestRow(
        filename=fasta.name,
        gff_filename=gff.name if gff else None,
        source="NCBI",
        accession=accession,
        assembly_name=assembly_name,
        release_version=None,
        species=species or assembly_name.split()[0] if assembly_name else None,
        strain=strain or (assembly_name.split()[1] if assembly_name and len(assembly_name.split()) > 1 else None),
        alias=alias,
        md5sum_fasta=md5_fasta,
        md5sum_gff=md5_gff,
        num_bases=sequence_length(fasta),
        num_contigs=contig_count(fasta),
        gc_percent=gc_percent(fasta),
        date_added=manifest_obj.today_iso(),
        sequencing_technology=seq_tech,
        bioproject=bioproject,
        biosample=biosample,
        notes=None,
    )

    if force:
        manifest_obj.replace_by_accession(accession, row)
        click.echo(f"Updated {accession} in manifest")
    else:
        manifest_obj.append(row)
        click.echo(f"Added {accession} to manifest")


@cli.command()
@click.argument("fasta", type=click.Path(exists=True))
@click.argument("gff", type=click.Path(exists=True), required=False)
@click.option("--species", help="Species name")
@click.option("--strain", help="Strain name")
@click.option("--alias", help="Short alias")
@click.option("--outdir", type=click.Path(), default="MyAssemblies", help="Destination directory")
@click.option("--manifest", type=click.Path(), default="manifest.csv", help="Manifest CSV")
def add(fasta, gff, species, strain, alias, outdir, manifest):
    """Add local fasta/gff files to database and manifest.

    Usage:
      leishref add /path/to/assembly.fa --species Leishmania_major --strain myStrain
      leishref add assembly.fa assembly.gff --alias MyGenome
    """
    fasta = Path(fasta)
    gff = Path(gff) if gff else None
    outdir = Path(outdir)
    manifest_obj = Manifest(Path(manifest))

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
        date_added=manifest_obj.today_iso(),
        notes="added locally",
    )

    manifest_obj.append(row)
    click.echo(f"Added to manifest: {new_fasta.name}")


@cli.command()
@click.option("--query", type=click.Path(exists=True), required=True, help="Query fasta file")
@click.option("--reference", required=True, help="Reference alias or filename")
@click.option("--outdir", type=click.Path(), default="Scaffold", help="Output directory")
@click.option("--alias", help="Alias for this scaffold")
@click.option("--clean", is_flag=True, help="Keep only chr-anchored contigs + kinetoplast")
@click.option("--manifest", type=click.Path(), default="manifest.csv", help="Manifest CSV")
@click.option("--ragtag-bin", help="Path to ragtag.py (auto-detect if not given)")
def scaffold(query, reference, outdir, alias, clean, manifest, ragtag_bin):
    """Run ragtag scaffold on query against reference."""
    query = Path(query)
    outdir = Path(outdir)
    manifest_obj = Manifest(Path(manifest))

    ref_row = manifest_obj.find_by_alias(reference)
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
                date_added=manifest_obj.today_iso(),
                alias=alias,
            )
            manifest_obj.append(row_cleaned)
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
                date_added=manifest_obj.today_iso(),
                alias=alias,
            )
            manifest_obj.append(row)
            click.echo(f"Scaffold: {out_fasta.name}")

    finally:
        import shutil as sh

        sh.rmtree(tmp_outdir, ignore_errors=True)


@cli.command()
@click.option("--manifest", type=click.Path(), default="manifest.csv")
@click.option("--outdir", type=click.Path(), default=".", help="Base directory to scan")
@click.option("--dry-run", is_flag=True, help="Show what would be added, don't modify manifest")
def backfill(manifest, outdir, dry_run):
    """Scan existing files and backfill manifest."""
    outdir = Path(outdir)
    manifest_obj = Manifest(Path(manifest))
    existing_files = {r.get("filename") for r in manifest_obj.read() if r.get("filename")}

    new_rows = []

    click.echo("Scanning NCBI/...")
    for fpath in (outdir / "NCBI").glob("*.fa*"):
        if fpath.name in existing_files or fpath.name.endswith(".fai"):
            continue
        gff_name = fpath.stem + ".gff"
        gff_path = fpath.parent / gff_name
        md5_fa = md5_file(fpath)
        md5_gf = md5_file(gff_path) if gff_path.exists() else None
        row = ManifestRow(
            filename=fpath.name,
            gff_filename=gff_name if gff_path.exists() else None,
            source="NCBI",
            md5sum_fasta=md5_fa,
            md5sum_gff=md5_gf,
            date_added=manifest_obj.today_iso(),
            notes="backfilled from disk",
        )
        new_rows.append(row)
        click.echo(f"  {fpath.name}")

    click.echo("Scanning MyAssemblies/...")
    for fpath in (outdir / "MyAssemblies").rglob("*.fa*"):
        if fpath.suffix in [".fai"] or fpath.name in existing_files:
            continue
        md5_fa = md5_file(fpath)
        agp_name = fpath.with_suffix(".agp").name
        agp_path = fpath.parent / agp_name
        row = ManifestRow(
            filename=fpath.name,
            source="MyAssembly",
            md5sum_fasta=md5_fa,
            species=fpath.parent.name.split(".")[0] if "." in fpath.parent.name else fpath.parent.name,
            strain=fpath.parent.name,
            date_added=manifest_obj.today_iso(),
            notes="backfilled from disk",
        )
        new_rows.append(row)
        click.echo(f"  {fpath.name}")

    click.echo("Scanning Scaffold/...")
    for fpath in (outdir / "Scaffold").glob("*.fa*"):
        if fpath.suffix in [".fai"] or fpath.name in existing_files:
            continue
        md5_fa = md5_file(fpath)
        agp_name = fpath.with_suffix(".agp").name
        agp_path = fpath.parent / agp_name
        row = ManifestRow(
            filename=fpath.name,
            source="Scaffold",
            md5sum_fasta=md5_fa,
            scaffold_tool_version="ragtag.py",
            cleaned="cleaned" in fpath.name,
            date_added=manifest_obj.today_iso(),
            notes="backfilled from disk",
        )
        new_rows.append(row)
        click.echo(f"  {fpath.name}")

    if dry_run:
        click.echo(f"\nWould add {len(new_rows)} rows to manifest (dry-run)")
    else:
        manifest_obj.append_many(new_rows)
        click.echo(f"\nAdded {len(new_rows)} rows to manifest")


@cli.command()
@click.argument("scaffold", type=click.Path(exists=True))
@click.option("--manifest", type=click.Path(), default="manifest.csv")
@click.option("--version", help="Version tag (e.g., v1.0)")
@click.option("--confirm", is_flag=True, help="Actually publish (else dry-run)")
@click.option("--sandbox", is_flag=True, help="Publish to sandbox.zenodo.org (test)")
def publish(scaffold, manifest, version, confirm, sandbox):
    """Publish scaffold (fasta+agp) to Zenodo. Requires ZENODO_TOKEN env var."""
    scaffold = Path(scaffold)
    manifest_obj = Manifest(Path(manifest))

    # Find corresponding AGP file
    agp_file = scaffold.with_suffix(".agp")
    if not agp_file.exists():
        click.echo(f"AGP file not found: {agp_file}", err=True)
        return

    # Check if already published
    row = manifest_obj.find_by_filename(scaffold.name)
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

        # Update manifest (production only, not sandbox)
        if not sandbox:
            if row:
                row["zenodo_doi"] = doi
                manifest_obj.replace_by_accession(row.get("accession"), row)
            else:
                new_row = ManifestRow(
                    filename=scaffold.name,
                    gff_filename=agp_file.name,
                    source="Scaffold",
                    zenodo_doi=doi,
                    version=version,
                    date_added=manifest_obj.today_iso(),
                )
                manifest_obj.append(new_row)
            click.echo(f"Updated manifest.csv")
        else:
            click.echo("Sandbox publish (manifest not updated)")

    except ZenodoError as e:
        click.echo(f"Zenodo error: {e}", err=True)
        return


@cli.command()
@click.option("--manifest", type=click.Path(), default="manifest.csv")
@click.option("--alias", help="Look up specific alias")
def info(manifest, alias):
    """Display manifest info with provenance. Warn about untracked files."""
    manifest_obj = Manifest(Path(manifest))
    rows = manifest_obj.read()

    if alias:
        row = manifest_obj.find_by_alias(alias)
        if row:
            for k, v in row.items():
                click.echo(f"{k}: {v}")
        else:
            click.echo(f"Alias not found: {alias}", err=True)
    else:
        click.echo(f"Total genomes: {len(rows)}\n")
        for row in rows:
            filename = row.get("filename", "N/A")
            alias_name = row.get("alias") or "(no alias)"
            source = row.get("source", "?")
            accession = row.get("accession") or ""
            zenodo = row.get("zenodo_doi") or ""
            release_ver = row.get("release_version") or ""

            click.echo(f"{filename}")
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
        for datadir in ["NCBI", "MyAssemblies", "Scaffold", "TriTryDB68"]:
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
