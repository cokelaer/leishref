"""CLI entry points for leishdb."""

import shutil
import tempfile
from pathlib import Path

import click

from leishdb.aliases import Aliases
from leishdb.checksums import contig_count, md5_file, sequence_length
from leishdb.manifest import Manifest, ManifestRow
from leishdb.ncbi import fetch_fasta_gff, fetch_metadata
from leishdb.scaffold import clean_scaffolded_fasta, parse_agp, run_scaffold
from leishdb.tritrypdb import download_fasta_gff as tritrypdb_download


@click.group()
def cli():
    """Leishmania genome database."""
    pass


@cli.command()
@click.option("--accession", required=True, help="NCBI accession (e.g., GCA_000410715.1)")
@click.option("--species", help="Species name (inferred from NCBI if not given)")
@click.option("--strain", help="Strain name (inferred from NCBI if not given)")
@click.option("--alias", help="Short alias for this genome")
@click.option("--outdir", type=click.Path(), default="NCBI", help="Output directory")
@click.option("--manifest", type=click.Path(), default="manifest.csv", help="Manifest CSV")
def fetch_cmd(accession, species, strain, alias, outdir, manifest):
    """Fetch genome from NCBI, optionally check TriTrypDB."""
    outdir = Path(outdir)
    manifest_obj = Manifest(Path(manifest))

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
        date_added=manifest_obj.today_iso(),
        sequencing_technology=seq_tech,
        bioproject=bioproject,
        biosample=biosample,
        notes=None,
    )

    manifest_obj.append(row)
    click.echo(f"Added {accession} to manifest")


@cli.command()
@click.option("--query", type=click.Path(exists=True), required=True, help="Query fasta file")
@click.option("--reference", required=True, help="Reference alias or filename")
@click.option("--outdir", type=click.Path(), default="Scaffold", help="Output directory")
@click.option("--alias", help="Alias for this scaffold")
@click.option("--clean", is_flag=True, help="Keep only chr-anchored contigs + kinetoplast")
@click.option("--manifest", type=click.Path(), default="manifest.csv", help="Manifest CSV")
@click.option("--ragtag-bin", help="Path to ragtag.py (auto-detect if not given)")
def scaffold_cmd(query, reference, outdir, alias, clean, manifest, ragtag_bin):
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
def backfill_cmd(manifest, outdir, dry_run):
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
@click.option("--scaffold", type=click.Path(exists=True), required=True, help="Scaffold fasta file")
@click.option("--manifest", type=click.Path(), default="manifest.csv")
@click.option("--confirm", is_flag=True, help="Actually publish (else dry-run)")
def publish_cmd(scaffold, manifest, confirm):
    """Publish scaffold to Zenodo (requires ZENODO_TOKEN)."""
    scaffold = Path(scaffold)
    click.echo(f"Zenodo publishing: {scaffold.name} (dry-run, add --confirm to publish)")
    click.echo("Requires ZENODO_TOKEN env var")
    if confirm:
        click.echo("Publishing... (not yet implemented)")


@cli.command()
@click.option("--manifest", type=click.Path(), default="manifest.csv")
@click.option("--alias", help="Look up specific alias")
def info_cmd(manifest, alias):
    """Display manifest info."""
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
        click.echo(f"Total genomes: {len(rows)}")
        for row in rows:
            click.echo(f"  {row.get('filename', 'N/A')}: {row.get('alias', 'N/A')}")


if __name__ == "__main__":
    cli()
