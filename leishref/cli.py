"""CLI entry points for leishref.

Top-level commands are for using the database. Maintaining the shipped catalog is a
different job with different risks, so those commands live under ``leishref dev``.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import rich_click as click

from leishref.agp import derive_agp, write_agp
from leishref.checksums import contig_count, gc_percent, md5_file, sequence_length
from leishref.links import LinkConflict, link_paths
from leishref.metadata import CATALOG_DIR, LOCAL_DIR, Genome, catalog, find, local, read_genome, today_iso, write_genome
from leishref.ncbi import fetch_fasta_gff, fetch_metadata
from leishref.scaffold import clean_scaffolded_fasta, run_scaffold
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


@cli.group()
def dev():
    """Commands for maintaining the shipped catalog.

    These write to leishref/data/, the catalog that ships with the package. Changes
    there are meant to travel as a pull request.
    """


# --------------------------------------------------------------------------- helpers


def _stats(fasta: Path) -> dict:
    return {
        "num_bases": sequence_length(fasta),
        "num_contigs": contig_count(fasta),
        "gc_percent": gc_percent(fasta),
    }


def _link(alias: str, paths, no_link: bool) -> None:
    if no_link:
        return
    try:
        for link in link_paths(alias, paths):
            click.echo(f"  {link.name} -> {os.readlink(link)}")
    except LinkConflict as exc:
        click.echo(f"  not linked: {exc}", err=True)


def _install(genome: Genome, alias: str, sources, local_root: Path, move: bool = False) -> Path:
    """Put a genome into the local database at data/<alias>/, metadata and files together.

    The installed copy takes the alias as its identifier, since locally the directory
    name is the name. Where it came from is kept under provenance so the link back to
    the catalog entry survives.
    """
    target = Path(local_root) / alias
    target.mkdir(parents=True, exist_ok=True)

    genome = Genome.from_dict(genome.to_dict())
    if genome.identifier and genome.identifier != alias:
        genome.provenance = dict(genome.provenance)
        genome.provenance["catalog_id"] = genome.identifier
    genome.identifier = alias

    for path in sources:
        if path is None:
            continue
        path = Path(path)
        destination = target / path.name
        if path.resolve() == destination.resolve():
            continue
        if move:
            shutil.move(str(path), destination)
        else:
            shutil.copy2(path, destination)

    write_genome(target, genome)
    return target


def _require(genomes, key, what):
    genome = find(genomes, key)
    if genome is None:
        click.echo(f"Not in {what}: {key}", err=True)
        click.echo("Run 'leishref info' to see what is available", err=True)
        raise SystemExit(1)
    return genome


# ----------------------------------------------------------------------- user commands


@cli.command()
@click.argument("name")
@click.option("--alias", required=True, help="Name for this genome in your local database")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--catalog-dir", type=click.Path(), help="Read the catalog from here instead")
@click.option("--force", is_flag=True, help="Download again even if already installed")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def download(name, alias, local_dir, catalog_dir, force, no_link):
    """Install a catalog genome into the local database under ALIAS.

    NAME picks the genome out of the catalog by accession or catalog id. ALIAS is the
    name it takes locally: it becomes the directory under data/ and the symlink name,
    so it is yours to choose and required.

    Examples:
      leishref download GCA_000410715.1 --alias Ltrop.L590
      leishref download Ltropica.Ld1S.scaffold.flye --alias flye
    """
    entries = catalog(Path(catalog_dir) if catalog_dir else None)
    genome = _require(entries, name, "catalog")

    target = Path(local_dir) / alias
    if (target / "metadata.yaml").exists() and not force:
        click.echo(f"Already installed: {target}")
        _link(alias, [p for _, p, _ in read_genome(target).file_paths() if p.exists()], no_link)
        click.echo("Use --force to download again")
        return

    doi = genome.zenodo_doi
    accession = genome.accession

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if doi:
            click.echo(f"{name} -> {doi} (Zenodo)")
            written = download_record_files(record_id_from_doi(doi), tmp, sandbox=is_sandbox_doi(doi))
        elif accession:
            click.echo(f"{name} -> {accession} (NCBI)")
            fasta, gff = fetch_fasta_gff(accession, tmp)
            if not fasta:
                click.echo(f"NCBI has no data for {accession}", err=True)
                raise SystemExit(1)
            written = [p for p in (fasta, gff) if p]
        else:
            click.echo(f"{name} records neither a Zenodo DOI nor an NCBI accession", err=True)
            if genome.source == "TriTrypDB":
                click.echo("TriTrypDB needs a login; download by hand, then 'leishref dev add'", err=True)
            raise SystemExit(1)

        installed = _install(genome, alias, written, Path(local_dir))

    click.echo(f"Installed into {installed}")

    bad = False
    for kind, path, recorded in read_genome(installed).file_paths():
        if not path.exists():
            continue
        if recorded and md5_file(path) != recorded:
            click.echo(f"  md5 MISMATCH: {path.name}", err=True)
            bad = True
        elif recorded:
            click.echo(f"  md5 OK: {path.name}")

    _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)
    if bad:
        raise SystemExit(1)


@cli.command()
@click.argument("name", required=False)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--catalog-dir", type=click.Path(), help="Read the catalog from here instead")
def info(name, local_dir, catalog_dir):
    """List the catalog and the local database, or show one genome in full.

    Examples:
      leishref info
      leishref info GCA_000410715.1
    """
    entries = catalog(Path(catalog_dir) if catalog_dir else None)
    installed = local(Path(local_dir))

    if name:
        genome = find(installed, name) or _require(entries, name, "catalog")
        import yaml

        click.echo(yaml.safe_dump(genome.to_dict(), sort_keys=False, default_flow_style=False).rstrip())
        if genome.path:
            click.echo(f"\npath: {genome.path}")
        return

    click.echo(f"Catalog: {len(entries)} genomes  ({CATALOG_DIR})")
    for genome in entries:
        species = genome.species or "?"
        strain = f" {genome.strain}" if genome.strain else ""
        doi = "  zenodo" if genome.zenodo_doi else ""
        click.echo(f"  {genome.identifier:<38} {species}{strain}{doi}")

    click.echo(f"\nLocal: {len(installed)} installed  ({Path(local_dir)})")
    for genome in installed:
        click.echo(f"  {genome.identifier:<38} {genome.species or '?'}")
    if not installed:
        click.echo("  (nothing yet -- 'leishref download <name> --alias <alias>')")


@cli.command()
@click.argument("terms", nargs=-1, required=True)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--catalog-dir", type=click.Path(), help="Read the catalog from here instead")
@click.option("--installed", is_flag=True, help="Only genomes already in the local database")
@click.option("--long", "long_form", is_flag=True, help="Show the full record for each match")
def search(terms, local_dir, catalog_dir, installed, long_form):
    """Find catalog genomes matching every TERM.

    Terms are matched case-insensitively against the whole record: species, strain,
    accession, taxon id, assembly name, filenames and provenance. Several terms narrow
    the result rather than widening it.

    Examples:
      leishref search donovani
      leishref search tropica zenodo
      leishref search 5661
      leishref search PRJNA450813
    """
    entries = catalog(Path(catalog_dir) if catalog_dir else None)
    here = local(Path(local_dir))

    # A local install records where it came from, so matches can be flagged as present.
    by_origin = {}
    for genome in here:
        origin = genome.provenance.get("catalog_id") or genome.identifier
        by_origin[origin] = genome.identifier

    matches = [g for g in entries if g.matches(terms)]
    if installed:
        matches = [g for g in matches if g.identifier in by_origin]

    query = " ".join(terms)
    if not matches:
        click.echo(f"No genome matches {query!r}")
        click.echo("Run 'leishref info' to list the catalog")
        raise SystemExit(1)

    click.echo(f"{len(matches)} match{'es' if len(matches) > 1 else ''} for {query!r}\n")

    if long_form:
        import yaml

        for genome in matches:
            click.echo(yaml.safe_dump(genome.to_dict(), sort_keys=False, default_flow_style=False).rstrip())
            click.echo("")
        return

    for genome in matches:
        organism = " ".join(filter(None, (genome.species, genome.strain))) or "?"
        bases = genome.stats.get("num_bases")
        size = f"{bases / 1e6:.1f} Mb" if bases else ""
        contigs = genome.stats.get("num_contigs")
        seqs = f"{contigs} seqs" if contigs else ""
        flags = []
        if genome.zenodo_doi:
            flags.append("zenodo")
        if genome.identifier in by_origin:
            flags.append(f"installed as {by_origin[genome.identifier]}")
        suffix = f"  [{', '.join(flags)}]" if flags else ""

        click.echo(f"  {genome.identifier:<38} {organism:<28} {genome.source or '?':<11} {size:>8} {seqs:>10}{suffix}")


@cli.command()
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--quick", is_flag=True, help="Check presence only, skip checksums")
def verify(local_dir, quick):
    """Check the local database against the checksums recorded with each genome.

    Examples:
      leishref verify
      leishref verify --quick
    """
    installed = local(Path(local_dir))
    ok, missing, mismatch = 0, [], []

    for genome in installed:
        for kind, path, recorded in genome.file_paths():
            if not path.exists():
                missing.append((genome.identifier, path))
            elif quick or not recorded:
                ok += 1
            elif md5_file(path) != recorded:
                mismatch.append((genome.identifier, path))
            else:
                ok += 1

    click.echo(f"Checked {len(installed)} installed genomes")
    click.echo(f"  ok:       {ok}")
    click.echo(f"  missing:  {len(missing)}")
    click.echo(f"  mismatch: {len(mismatch)}")

    for label, entries in (("MISSING", missing), ("CHECKSUM MISMATCH", mismatch)):
        if entries:
            click.echo(f"\n{label}:", err=True)
            for identifier, path in entries:
                click.echo(f"  {identifier}: {path}", err=True)

    if missing or mismatch:
        raise SystemExit(1)


@cli.command()
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--basedir", type=click.Path(), default=".", help="Where to create the links")
def link(local_dir, basedir):
    """Refresh the alias-named symlinks for everything installed locally.

    Examples:
      leishref link
    """
    made, conflicts = [], []
    for genome in local(Path(local_dir)):
        paths = [p for _, p, _ in genome.file_paths() if p.exists()]
        try:
            made.extend(link_paths(genome.identifier, paths, Path(basedir)))
        except LinkConflict as exc:
            conflicts.append(str(exc))

    for created in made:
        click.echo(f"  {created.name} -> {os.readlink(created)}")
    click.echo(f"\nCreated {len(made)} links")

    if conflicts:
        click.echo("\nNot linked:", err=True)
        for conflict in conflicts:
            click.echo(f"  {conflict}", err=True)


# ------------------------------------------------------------------------ dev commands


@dev.command()
@click.argument("accession")
@click.option("--alias", help="Also install into the local database under this name")
@click.option("--species", help="Override the species reported by NCBI")
@click.option("--strain", help="Override the strain reported by NCBI")
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Replace an existing catalog entry")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def fetch(accession, alias, species, strain, catalog_dir, local_dir, force, no_link):
    """Add an NCBI genome to the catalog.

    Downloads the assembly to record its checksums and statistics. Pass --alias to keep
    the files in the local database rather than discarding them.

    Examples:
      leishref dev fetch GCA_000410715.1
      leishref dev fetch GCA_000410715.1 --alias Ltrop.L590
    """
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    entry = root / accession
    if (entry / "metadata.yaml").exists() and not force:
        click.echo(f"Already in the catalog: {entry}", err=True)
        click.echo("Use --force to replace it", err=True)
        raise SystemExit(1)

    click.echo(f"Fetching {accession} from NCBI...")
    with tempfile.TemporaryDirectory() as tmp:
        fasta, gff = fetch_fasta_gff(accession, Path(tmp))
        if not fasta:
            click.echo(f"Not found on NCBI: {accession}", err=True)
            raise SystemExit(1)

        meta = fetch_metadata(accession)
        organism = (meta.get("organism_name") or "").split()

        genome = Genome(
            identifier=accession,
            source="NCBI",
            accession=accession,
            taxon_id=meta.get("taxon_id"),
            species=species or (" ".join(organism[:2]) if len(organism) >= 2 else None),
            strain=strain or (" ".join(organism[2:]) or None),
            assembly_name=meta.get("assembly_name"),
            files={k: v.name for k, v in (("fasta", fasta), ("gff", gff)) if v},
            checksums={k: md5_file(v) for k, v in (("fasta", fasta), ("gff", gff)) if v},
            stats=_stats(fasta),
            provenance={
                k: v
                for k, v in (
                    ("bioproject", meta.get("bioproject")),
                    ("biosample", meta.get("biosample")),
                    ("sequencing_technology", meta.get("sequencing_technology")),
                )
                if v
            },
            date_added=today_iso(),
        )

        write_genome(entry, genome)
        click.echo(f"Catalog entry: {entry}")

        if alias:
            installed = _install(genome, alias, [fasta, gff], Path(local_dir))
            click.echo(f"Installed into {installed}")
            _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


@dev.command()
@click.argument("fasta", type=click.Path(exists=True))
@click.argument("gff", type=click.Path(exists=True), required=False)
@click.option("--alias", required=True, help="Name for this genome, in the catalog and locally")
@click.option("--species", help="Species name")
@click.option("--strain", help="Strain name")
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def add(fasta, gff, alias, species, strain, catalog_dir, local_dir, no_link):
    """Add a local assembly to the catalog and install it locally.

    Examples:
      leishref dev add assembly.fa --alias Ltrop.flye --species "Leishmania tropica"
      leishref dev add assembly.fa assembly.gff --alias Ltrop.flye
    """
    fasta, gff = Path(fasta), Path(gff) if gff else None
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR

    genome = Genome(
        identifier=alias,
        source="MyAssembly",
        species=species,
        strain=strain,
        files={k: v.name for k, v in (("fasta", fasta), ("gff", gff)) if v},
        checksums={k: md5_file(v) for k, v in (("fasta", fasta), ("gff", gff)) if v},
        stats=_stats(fasta),
        date_added=today_iso(),
    )

    write_genome(root / alias, genome)
    click.echo(f"Catalog entry: {root / alias}")

    installed = _install(genome, alias, [fasta, gff], Path(local_dir))
    click.echo(f"Installed into {installed}")
    _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


@dev.command()
@click.option("--query", type=click.Path(exists=True), required=True, help="Assembly to scaffold")
@click.option("--reference", required=True, help="Reference genome, by catalog id or local alias")
@click.option("--alias", required=True, help="Name for the resulting scaffold")
@click.option("--clean", is_flag=True, help="Keep only chr-anchored contigs plus kinetoplast")
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def scaffold(query, reference, alias, clean, catalog_dir, local_dir, no_link):
    """Scaffold an assembly against a reference with ragtag.

    Examples:
      leishref dev scaffold --query flye.fa --reference Ltrop.L590 --alias Ltrop.flye
      leishref dev scaffold --query flye.fa --reference Ltrop.L590 --alias Ltrop.flye --clean
    """
    query = Path(query)
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    local_root = Path(local_dir)

    ref = find(local(local_root), reference) or find(catalog(Path(catalog_dir) if catalog_dir else None), reference)
    if ref is None or ref.path is None or not ref.fasta:
        click.echo(f"Reference not available locally: {reference}", err=True)
        click.echo(f"Install it first: leishref download {reference} --alias {reference}", err=True)
        raise SystemExit(1)

    ref_fasta = ref.path / ref.fasta
    if not ref_fasta.exists():
        click.echo(f"Reference file missing: {ref_fasta}", err=True)
        raise SystemExit(1)

    click.echo(f"Scaffolding {query.name} onto {reference}...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        scaffold_fasta, scaffold_agp = run_scaffold(ref_fasta, query, tmp)

        result = tmp / f"{alias}.fa"
        if clean:
            result.write_text(clean_scaffolded_fasta(scaffold_fasta, scaffold_agp))
        else:
            shutil.copy(scaffold_fasta, result)
        agp = tmp / f"{alias}.agp"
        shutil.copy(scaffold_agp, agp)

        genome = Genome(
            identifier=alias,
            source="Scaffold",
            species=ref.species,
            strain=ref.strain,
            files={"fasta": result.name},
            checksums={"fasta": md5_file(result)},
            stats=_stats(result),
            provenance={"agp_filename": agp.name},
            scaffold={
                "reference_alias": reference,
                "tool_version": "ragtag.py",
                "cleaned": True if clean else None,
            },
            date_added=today_iso(),
        )
        genome.scaffold = {k: v for k, v in genome.scaffold.items() if v is not None}

        write_genome(root / alias, genome)
        click.echo(f"Catalog entry: {root / alias}")

        installed = _install(genome, alias, [result, agp], local_root, move=True)

    click.echo(f"Installed into {installed}")
    _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


@dev.command()
@click.argument("name")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--catalog-dir", type=click.Path(), help="Update the entry here instead")
@click.option("--version", help="Version tag, e.g. v1.0")
@click.option("--confirm", is_flag=True, help="Actually publish, rather than dry-run")
@click.option("--sandbox", is_flag=True, help="Publish to sandbox.zenodo.org")
def publish(name, local_dir, catalog_dir, version, confirm, sandbox):
    """Deposit an installed genome's files on Zenodo and record the DOI.

    Needs ZENODO_TOKEN, or ZENODO_SANDBOX_TOKEN with --sandbox.

    Examples:
      leishref dev publish Ltrop.flye
      leishref dev publish Ltrop.flye --confirm --version v1.0
    """
    genome = _require(local(Path(local_dir)), name, "local database")
    payload = [p for _, p, _ in genome.file_paths() if p.exists()]
    agp = genome.provenance.get("agp_filename")
    if agp and (genome.path / agp).exists():
        payload.append(genome.path / agp)

    if genome.zenodo_doi:
        click.echo(f"Already published: {genome.zenodo_doi}", err=True)
        raise SystemExit(1)

    if not confirm:
        click.echo(f"Dry-run: would publish {', '.join(p.name for p in payload)}")
        click.echo("Add --confirm to publish")
        return

    try:
        title = f"Leishmania genome: {genome.identifier}"
        deposition = create_deposition(title, title, ["Leishmania Database"], sandbox=sandbox)
        click.echo(f"Created deposition {deposition['id']}")

        for path in payload:
            click.echo(f"Uploading {path.name}...")
            upload_file(deposition["id"], path, sandbox=sandbox)

        update_metadata(
            deposition["id"],
            {
                "metadata": {
                    "title": deposition["metadata"]["title"],
                    "creators": deposition["metadata"]["creators"],
                    "version": version or "v1.0",
                    "keywords": ["leishmania", "genome", "assembly"],
                    "upload_type": "dataset",
                }
            },
            sandbox=sandbox,
        )
        published = publish_deposition(deposition["id"], sandbox=sandbox)
    except ZenodoError as exc:
        click.echo(f"Zenodo error: {exc}", err=True)
        raise SystemExit(1)

    doi = published.get("doi") or published.get("conceptdoi")
    click.echo(f"Published: {doi}")

    if sandbox:
        click.echo("Sandbox publish; catalog not updated")
        return

    genome.provenance["zenodo_doi"] = doi
    if version:
        genome.release_version = version
    write_genome(genome.path, genome)

    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    entry = root / genome.identifier
    if (entry / "metadata.yaml").exists():
        shipped = read_genome(entry)
        shipped.provenance["zenodo_doi"] = doi
        write_genome(entry, shipped)
        click.echo(f"Recorded DOI in {entry}")


@dev.command("derive-agp")
@click.argument("parent", type=click.Path(exists=True))
@click.argument("child", type=click.Path(exists=True))
@click.option("--out", type=click.Path(), help="AGP output path (default AGP/<child stem>.agp)")
@click.option("--record", help="Record the derivation on this local genome")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--probe-len", default=60, show_default=True, help="Anchor length used to locate blocks")
def derive_agp_cmd(parent, child, out, record, local_dir, probe_len):
    """Derive an AGP showing how CHILD was laid out from PARENT sequences.

    Reconstructs order, orientation and gaps of a re-scaffolded assembly relative to its
    source, so a third-party layout can be stored as coordinates rather than sequence.

    Examples:
      leishref dev derive-agp parent.fna child.fasta
      leishref dev derive-agp parent.fna child.fasta --record Ltrop.tritryp68
    """
    parent, child = Path(parent), Path(child)
    click.echo("Deriving layout (this scans both assemblies)...")
    lines, stats = derive_agp(parent, child, probe_len=probe_len)

    out_path = Path(out) if out else Path("AGP") / f"{child.stem}.agp"
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
        genome = _require(local(Path(local_dir)), record, "local database")
        genome.provenance["derived_from"] = parent.name
        genome.provenance["agp_filename"] = out_path.name
        write_genome(genome.path, genome)
        click.echo(f"Recorded derivation on {genome.identifier}")


if __name__ == "__main__":
    cli()
