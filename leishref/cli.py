"""CLI entry points for leishref.

Top-level commands are for using the database. Maintaining the shipped catalog is a
different job with different risks, so those commands live under ``leishref dev``.
"""

import concurrent.futures
import contextlib
import fnmatch
import io
import os
import shutil
import tarfile
import tempfile
import textwrap
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from tqdm import tqdm

from leishref.checksums import genome_stats, md5_file
from leishref.chromosomes import get_chromosome_info, rename_fasta_sequences
from leishref.links import LinkConflict, link_paths
from leishref.metadata import (
    CATALOG_DIR,
    LOCAL_DIR,
    Genome,
    catalog,
    catalog_entry_dir,
    catalog_group,
    find,
    get_catalog_alias,
    is_glob,
    load_aliases,
    local,
    read_genome,
    today_iso,
    write_genome,
)
from leishref.naming import suggest_alias
from leishref.ncbi import fetch_fasta_gff, fetch_metadata, species_from_organism
from leishref.nuccore import NuccoreError, fetch_nucleotide_fasta, fetch_nucleotide_metadata
from leishref.prune import prune_fasta
from leishref.scaffold import clean_scaffolded_fasta, ragtag_version, run_scaffold
from leishref.visualize import (
    plot_chromosome_length_histogram,
    plot_genome_size_histogram,
    plot_genome_sizes,
    plot_genome_stats,
)
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

# --------------------------------------------------------------------------- help style

# rich-click renders the help screens; everything below is presentation only.
click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = False
click.rich_click.TEXT_PARAGRAPH_LINEBREAKS = "\n\n"
click.rich_click.COMMANDS_BEFORE_OPTIONS = True
click.rich_click.MAX_WIDTH = 110
click.rich_click.STYLE_OPTION = "bold cyan"
click.rich_click.STYLE_ARGUMENT = "bold cyan"
click.rich_click.STYLE_COMMAND = "bold cyan"
click.rich_click.STYLE_SWITCH = "bold green"
click.rich_click.STYLE_METAVAR = "dim yellow"
click.rich_click.STYLE_OPTION_DEFAULT = "dim"
click.rich_click.STYLE_USAGE = "bold yellow"
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "bold"
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "dim cyan"
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "dim cyan"
click.rich_click.STYLE_ERRORS_PANEL_BORDER = "red"
click.rich_click.ERRORS_SUGGESTION = "Try 'leishref COMMAND --help' for the options of a command."

# Using the database is one job, maintaining the shipped catalog is another; the two
# groups of commands are kept in separate panels so the split is visible in --help.
click.rich_click.COMMAND_GROUPS = {
    "leishref": [
        {
            "name": "Using the database",
            "commands": [
                "search",
                "info",
                "install",
                "install-ncbi",
                "install-ncbi-refseq",
                "restore",
                "verify",
                "rename-sequences",
                "prune-scaffold",
                "bundle",
                "export",
            ],
        },
        {
            "name": "For maintainers and developers",
            "commands": ["dev", "link"],
        },
        {
            "name": "Plotting",
            "commands": ["plot-stats", "plot-sizes", "plot-histogram", "plot-chromosome-histogram"],
        },
    ],
    "leishref dev": [
        {
            "name": "Adding genomes",
            "commands": ["fetch-genome", "fetch-nucleotide", "add", "scaffold", "derive-agp"],
        },
        {
            "name": "Publishing and managing",
            "commands": ["publish", "remove"],
        },
    ],
}

# Options that say *where* to read and write are the same everywhere and are noise next
# to the options that change what a command does, so they get their own panel.
_LOCATION_OPTIONS = {
    "name": "Where to read and write",
    "options": ["--local-dir", "--basedir", "--workdir", "--out"],
}

click.rich_click.OPTION_GROUPS = {
    command: [{"name": "Options", "options": options}, _LOCATION_OPTIONS]
    for command, options in {
        "leishref search": ["--installed", "--long", "--help"],
        "leishref install": ["--alias", "--force", "--no-link", "--help"],
        "leishref verify": ["--quick", "--help"],
        "leishref restore": [
            "--file",
            "--from-installed",
            "--force",
            "--no-link",
            "--dry-run",
            "--verbose",
            "--help",
        ],
        "leishref dev fetch-genome": ["--alias", "--species", "--strain", "--force", "--no-link", "--help"],
        "leishref dev add": [
            "--fasta",
            "--gff",
            "--alias",
            "--species",
            "--strain",
            "--technology",
            "--assembler",
            "--no-link",
            "--help",
        ],
        "leishref dev publish": ["--version", "--confirm", "--sandbox", "--help"],
        "leishref dev scaffold": [
            "--query",
            "--reference",
            "--alias",
            "--species",
            "--strain",
            "--clean",
            "--no-link",
            "--help",
        ],
    }.items()
}


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


FASTA_SUFFIXES = (".fna", ".fa", ".fasta")


def _classify(paths) -> dict:
    """Sort written files into the roles metadata.yaml records."""
    roles = {}
    for path in paths:
        if path is None:
            continue
        suffix = Path(path).suffix.lower()
        if suffix in FASTA_SUFFIXES and "fasta" not in roles:
            roles["fasta"] = Path(path)
        elif suffix == ".gff" and "gff" not in roles:
            roles["gff"] = Path(path)
    return roles


SOURCE_STYLES = {
    "GenBank": "cyan",
    "RefSeq": "magenta",
    "Zenodo": "green",
    "TriTrypDB": "yellow",
    "Local": "dim",
    "Scaffold": "blue",
    "NCBI-Nucleotide": "cyan",
}


def _console(err: bool = False):
    """A rich console for command output.

    Styles are dropped automatically when the output is piped or captured, so the
    columns stay exactly as wide as before and remain safe to parse.
    """
    return Console(highlight=False, soft_wrap=True, stderr=err)


def _source_label(genome) -> str:
    """'GenBank' or 'RefSeq' for NCBI records, the source name otherwise.

    NCBI ships most assemblies twice: the submitter's GenBank copy (GCA_) and NCBI's
    own RefSeq copy (GCF_). They share the assembly name and the statistics, so both
    show up as plain 'NCBI' unless the accession prefix is spelled out.
    """
    source = genome.source or "?"
    if source != "NCBI":
        return source
    accession = genome.accession or genome.identifier or ""
    if accession.startswith("GCF_"):
        return "RefSeq"
    if accession.startswith("GCA_"):
        return "GenBank"
    return source


def _organism(genome) -> str:
    """'Leishmania donovani - BPK282A1', or just the species when no strain is known.

    An undescribed species is sometimes named after the very isolate it was found in, so
    the strain is dropped when the species already contains it.
    """
    species = genome.species or "?"
    strain = genome.strain
    if not strain or strain in species:
        return species
    return f"{species} - {strain}"


def _resolve_assembly(value, local_root: Path, cat_root, what: str):
    """A FASTA to scaffold with, given either a path or a genome name.

    Returns (path, genome or None). A name is looked up in the local database first.
    If not found locally but exists in the catalog, downloads it to a temporary
    directory. A plain path is taken as is with no metadata.
    """
    as_path = Path(value)
    if as_path.exists() and as_path.is_file():
        return as_path, None

    # Try local first
    genome = find(local(local_root), value, cat_root)
    if genome and genome.path and genome.fasta and (genome.path / genome.fasta).exists():
        return genome.path / genome.fasta, genome

    # Try catalog
    cat_genome = find(catalog(cat_root), value, cat_root)
    if cat_genome is None:
        click.echo(f"{what} is neither a file nor a known genome: {value}", err=True)
        raise SystemExit(1)

    # Download from catalog to temp directory
    if not cat_genome.fasta or not cat_genome.accession:
        click.echo(f"{what} is in catalog but has no downloadable FASTA: {value}", err=True)
        raise SystemExit(1)

    import tempfile

    tmp_dir = Path(tempfile.gettempdir()) / "leishref_scaffold" / cat_genome.identifier
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = tmp_dir / cat_genome.fasta

    if not fasta_path.exists():
        click.echo(f"Downloading {cat_genome.identifier} to temporary directory...")
        try:
            from leishref.ncbi import fetch_fasta_gff

            fetch_fasta_gff(cat_genome.accession, str(tmp_dir))
        except Exception as e:
            click.echo(f"Failed to download {cat_genome.identifier}: {e}", err=True)
            raise SystemExit(1)

    if not fasta_path.exists():
        click.echo(f"Download succeeded but FASTA file not found: {fasta_path}", err=True)
        raise SystemExit(1)

    return fasta_path, cat_genome


def _parent_record(path: Path, genome) -> dict:
    """What a published scaffold has to say about one of the assemblies it came from.

    The catalog identifier rather than a local alias, because an alias is renameable and
    machine-specific, and the md5 so the exact input can be recognised later.
    """
    record = {"file": path.name, "md5": md5_file(path)}
    if genome is None:
        return record
    record["name"] = genome.provenance.get("catalog_id") or genome.accession or genome.identifier
    for field in ("species", "strain", "assembly_level"):
        value = getattr(genome, field, None)
        if value:
            record[field] = value
    if genome.zenodo_doi:
        record["zenodo_doi"] = genome.zenodo_doi
    return record


def _genome_alias(genome: Genome, cat_root=None) -> str:
    """Short name for a genome: catalog alias if available, otherwise identifier.

    For TriTrypDB genomes, appends _tritryp suffix to the identifier to avoid collision
    with NCBI genomes.
    """
    if genome.source and genome.source.lower() == "tritrypdb":
        return f"{genome.identifier}_tritryp"
    return get_catalog_alias(genome.accession or "", cat_root) or genome.identifier


def _by_organism(genomes: list) -> list:
    """Group a listing by organism rather than by accession, which sorts arbitrarily."""
    return sorted(genomes, key=lambda g: ((g.species or "~").lower(), (g.strain or "").lower(), g.identifier))


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

    # Entries imported from NCBI's summary carry no filenames, because nothing was
    # downloaded to name. Record what actually arrived so verify and link can see it.
    roles = _classify(sources)
    if roles:
        genome.files = {kind: path.name for kind, path in roles.items()}

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


def _fetch_genome_files(genome: Genome, name: str, tmp: Path) -> tuple[list, str]:
    """Download a genome's files into tmp, without any click I/O.

    Thread-safe: NCBI's datasets CLI runs as a subprocess and Zenodo downloads go
    through `requests` directly to a per-call directory, so concurrent callers with
    distinct tmp dirs don't interfere. Returns (written_paths, error_message); exactly
    one of the two is truthy.
    """
    doi = genome.zenodo_doi
    accession = genome.accession
    if doi:
        written = download_record_files(record_id_from_doi(doi), tmp, sandbox=is_sandbox_doi(doi))
        return written, "" if written else "Zenodo record has no files"
    if accession:
        fasta, gff = fetch_fasta_gff(accession, tmp)
        if not fasta:
            return [], f"NCBI has no data for {accession}"
        return [p for p in (fasta, gff) if p], ""
    if genome.fasta and genome.path and (genome.path / genome.fasta).exists():
        written = [genome.path / genome.fasta]
        if genome.gff and (genome.path / genome.gff).exists():
            written.append(genome.path / genome.gff)
        return written, ""
    return [], f"{name} records neither a Zenodo DOI nor an NCBI accession"


def _install_many_parallel(pairs, local_dir: Path, force: bool, no_link: bool, workers: int, echo) -> list:
    """Download PAIRS of (genome, alias) concurrently, install sequentially as each lands.

    Network fetch is the slow part and is safe to parallelize (see _fetch_genome_files);
    the local install (file copy, metadata write, linking) stays on the main thread since
    it's fast and keeps output and accessions.txt writes race-free. Returns aliases that
    failed.
    """
    local_dir = Path(local_dir)
    todo = []
    for genome, alias in pairs:
        target = local_dir / alias
        if (target / "metadata.yaml").exists() and not force:
            echo(f"Already installed: {alias}")
            _link(alias, [p for _, p, _ in read_genome(target).file_paths() if p.exists()], no_link)
            _record_download(local_dir, genome.identifier or alias, alias)
        else:
            todo.append((genome, alias))

    failed = []
    if not todo:
        return failed

    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_pair = {}
            for genome, alias in todo:
                tmp = scratch / alias
                tmp.mkdir(parents=True, exist_ok=True)
                future = pool.submit(_fetch_genome_files, genome, alias, tmp)
                future_to_pair[future] = (genome, alias)

            for future in concurrent.futures.as_completed(future_to_pair):
                genome, alias = future_to_pair[future]
                try:
                    written, error = future.result()
                except Exception as exc:  # a network hiccup on one genome must not sink the batch
                    written, error = [], str(exc)

                if error:
                    echo(f"  {alias}: {error}")
                    failed.append(alias)
                    continue

                installed = _install(genome, alias, written, local_dir)
                echo(f"  {alias}: installed into {installed}")
                _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)
                _record_download(local_dir, genome.identifier or alias, alias)

    return failed


ACCESSIONS_FILE = "accessions.txt"

#: Catalog sections in 'info', in reading order: the upstream archives first, then what
#: was derived here. Scaffolds are locally-derived. Custom genomes are user-added.
#: Zenodo and local entries are everything else.
INFO_SECTIONS = {
    "ncbi": "NCBI",
    "ncbi_nucleotide": "NCBI Nucleotide",
    "tritrypdb": "TriTrypDB",
    "scaffolds": "Scaffolds",
    "custom": "Custom",
    "zenodo": "Zenodo",
    "local": "Other",
}


def _record_download(local_root: Path, name: str, alias: str) -> Path:
    """Append this download to ./accessions.txt in the current directory.

    One line per installed genome, ``<catalog identifier><TAB><alias>``: the two things
    'leishref restore' needs to repeat the install. The catalog identifier is stored
    rather than the shorthand that was typed, because an alias can be renamed in
    aliases.txt while the identifier stays valid. An alias is only ever installed once,
    so re-installing it rewrites its line rather than adding a second one.
    """
    path = Path.cwd() / ACCESSIONS_FILE
    header = [
        "# Genomes installed with 'leishref install', most recent last.",
        "# Format: catalog-identifier<TAB>alias    Replay with 'leishref restore'.",
    ]

    lines = []
    if path.exists():
        lines = [ln.rstrip("\n") for ln in path.read_text().splitlines()]
    kept = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    kept = [ln for ln in kept if ln.split("\t")[-1].strip() != alias]
    kept.append(f"{name}\t{alias}")

    path.write_text("\n".join(header + kept) + "\n")
    return path


def _read_accessions(path: Path):
    """The (name, alias) pairs recorded in an accessions file, in order."""
    pairs = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t") if "\t" in line else line.split()
        if len(fields) != 2:
            click.echo(f"{path}:{number}: expected 'name<TAB>alias', skipping: {line}", err=True)
            continue
        pairs.append((fields[0], fields[1]))
    return pairs


def _require(genomes, key, what, catalog_root=None):
    genome = find(genomes, key, catalog_root)
    if genome is None:
        click.echo(f"Not in {what}: {key}", err=True)
        click.echo("Run 'leishref info' to see what is available", err=True)
        raise SystemExit(1)
    return genome


# ----------------------------------------------------------------------- user commands


@cli.command("install")
@click.argument("name")
@click.option("--alias", help="Name for this genome (required)")
@click.option(
    "--local-dir",
    type=click.Path(),
    default=str(LOCAL_DIR),
    show_default=True,
    help="Cache directory for downloaded genomes",
)
@click.option("--force", is_flag=True, help="Re-download, or replace a different genome under this alias")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def install(name, alias, local_dir, force, no_link):
    """Download a catalog genome and cache it with ALIAS.

    NAME picks the genome out of the catalog by accession or catalog id. ALIAS is the
    name for the cached copy: becomes the directory under ~/.config/leishref/ and the
    symlink name, so it is yours to choose and required. Recorded in ./accessions.txt
    so 'leishref restore' can rebuild this later.

    Re-running install with the same NAME and ALIAS is a safe no-op: it just makes sure
    the symlink is in place. --force is only needed to force a fresh download, or to
    replace a *different* genome already cached under this ALIAS.

    Examples:

    \b
      leishref install GCA_000410715.1 --alias Ltrop.L590
      leishref install Ltropica.Ld1S.scaffold.flye --alias flye
    """
    entries = catalog()
    genome = _require(entries, name, "catalog")

    if not alias:
        click.echo("--alias is required: it names the cached genome,", err=True)
        click.echo("becoming the directory under ~/.config/leishref/ and the symlink name.\n", err=True)
        aliases = load_aliases()
        suggested = aliases.get(genome.identifier) or get_catalog_alias(genome.accession or "") or suggest_alias(genome)
        click.echo(f"  leishref install {name} --alias {suggested}", err=True)
        raise SystemExit(2)

    target = Path(local_dir) / alias
    if (target / "metadata.yaml").exists() and not force:
        existing = read_genome(target)
        existing_origin = existing.provenance.get("catalog_id") or existing.accession or existing.identifier
        if existing_origin != genome.identifier:
            click.echo(f"--alias {alias} is already used by a different genome: {existing_origin}", err=True)
            click.echo("Use --force to replace it", err=True)
            raise SystemExit(1)

        # Same genome already cached under this alias: nothing worth re-downloading,
        # so this is quiet unless the symlink itself needed fixing.
        click.echo(f"Already installed: {target}")
        _link(alias, [p for _, p, _ in existing.file_paths() if p.exists()], no_link)
        _record_download(Path(local_dir), genome.identifier or name, alias)
        return

    doi = genome.zenodo_doi
    accession = genome.accession

    # Show what we're about to install
    source_name = genome.accession or doi or name
    click.echo(f"Installing {source_name} → {target}")

    # Check if files already exist locally with correct checksums
    target = Path(local_dir) / alias
    if not force and target.exists() and genome.checksums:
        local_checksums = {}
        for kind, path, _ in genome.file_paths():
            if path and path.exists():
                local_checksums[kind] = md5_file(path)

        if all(local_checksums.get(k) == v for k, v in genome.checksums.items() if k in ("fasta", "gff")):
            click.echo("Files already present with correct checksums, skipping install")
            _link(alias, [p for _, p, _ in genome.file_paths() if p and p.exists()], no_link)
            return

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
        elif genome.fasta and genome.path and (genome.path / genome.fasta).exists():
            click.echo(f"{name} (from catalog)")
            written = [genome.path / genome.fasta]
            if genome.gff:
                gff_path = genome.path / genome.gff
                if gff_path.exists():
                    written.append(gff_path)
        else:
            click.echo(f"{name} records neither a Zenodo DOI nor an NCBI accession", err=True)
            if genome.source == "TriTrypDB":
                click.echo("TriTrypDB needs a login; get the file manually, then 'leishref dev add'", err=True)
            raise SystemExit(1)

        installed = _install(genome, alias, written, Path(local_dir))

    click.echo(f"Installed into {installed}")

    local_genome = read_genome(installed)
    bad = False
    computed = {}
    for kind, path, recorded in local_genome.file_paths():
        if not path.exists():
            continue
        digest = md5_file(path)
        computed[kind] = digest
        if not recorded:
            click.echo(f"  md5 recorded: {path.name}")
        elif digest == recorded:
            click.echo(f"  md5 OK: {path.name}")
        else:
            click.echo(f"  md5 MISMATCH: {path.name}", err=True)
            bad = True

    # A catalog entry built from NCBI's summary has no checksum until something has
    # actually fetched the files; keep what we just computed so verify has a baseline.
    if computed and not local_genome.checksums:
        local_genome.checksums = computed
        write_genome(installed, local_genome)

    _link(alias, [p for _, p, _ in local_genome.file_paths() if p.exists()], no_link)
    recorded_in = _record_download(Path(local_dir), genome.identifier or name, alias)
    click.echo(f"  recorded in {recorded_in}")
    if bad:
        raise SystemExit(1)


@cli.command()
@click.argument("name", required=False)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
def info(name, local_dir):
    """List the catalog and the cached database, or show one genome in full.

    Examples:

    \b
      leishref info
      leishref info GCA_000410715.1
    """
    entries = catalog()
    installed = local(Path(local_dir))

    if name:
        genome = find(installed, name) or _require(entries, name, "catalog")
        import yaml

        console = _console()
        console.print(
            Syntax(
                yaml.safe_dump(genome.to_dict(), sort_keys=False, default_flow_style=False).rstrip(),
                "yaml",
                background_color="default",
                word_wrap=True,
            )
        )
        if genome.path:
            console.print(f"\npath: [cyan]{escape(str(genome.path))}[/]")
        if find(installed, name) is None:
            console.print(f"suggested alias: [bold cyan]{escape(suggest_alias(genome))}[/]")
        return

    console = _console()
    console.print(f"[bold]Catalog:[/] [bold]{len(entries)}[/] genomes  [dim]({CATALOG_DIR})[/]")

    sections = {group: [] for group in INFO_SECTIONS}
    for genome in entries:
        group = catalog_group(genome)
        sections[group if group in sections else "other"].append(genome)

    for group, label in INFO_SECTIONS.items():
        console.print(f"  {label:<12} [bold]{len(sections[group]):>5}[/]")

    for group, label in INFO_SECTIONS.items():
        if not sections[group]:
            continue
        console.print(f"\n[bold]{label}[/] [dim]({len(sections[group])})[/]")
        for genome in _by_organism(sections[group]):
            doi = "[green]  zenodo[/]" if genome.zenodo_doi else ""
            alias = _genome_alias(genome)
            alias_txt = f"[dim] (alias: {escape(alias)})[/]" if alias != genome.identifier else ""
            console.print(
                f"  [bold cyan]{escape(genome.identifier):<38}[/] {escape(_organism(genome))}{doi}{alias_txt}"
            )

    console.print(f"\n[bold]Cached:[/] [bold]{len(installed)}[/] installed  [dim]({Path(local_dir)})[/]")
    for genome in _by_organism(installed):
        source_ref = genome.provenance.get("catalog_id") or genome.accession or ""
        console.print(
            f"  [bold cyan]{escape(genome.identifier):<38}[/] {escape(_organism(genome)):<50}"
            f" [dim]{escape(source_ref)}[/]"
        )
    if not installed:
        console.print("  [dim](nothing yet -- 'leishref install <name> --alias <alias>')[/]")


@cli.command()
@click.argument("terms", nargs=-1, required=True)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--installed", is_flag=True, help="Only genomes already in the cached database")
@click.option("--long", "long_form", is_flag=True, help="Show the full record for each match")
def search(terms, local_dir, installed, long_form):
    """Find catalog genomes matching every TERM.

    Terms are matched case-insensitively against the whole record: species, strain,
    accession, taxon id, assembly name, filenames and provenance. Several terms narrow
    the result rather than widening it.

    A term may be a wildcard pattern (* ? [...]); quote it so the shell does not expand
    it first. A lone '*' lists the whole catalog.

    Examples:

    \b
      leishref search donovani
      leishref search tropica zenodo
      leishref search 5661
      leishref search PRJNA450813
      leishref search '*'
      leishref search 'GCF_*' infantum
    """
    entries = catalog()
    here = local(Path(local_dir))

    # A cached install records where it came from, so matches can be flagged as present.
    by_origin = {}
    for genome in here:
        origin = genome.provenance.get("catalog_id") or genome.identifier
        by_origin[origin] = genome.identifier

    # Load aliases for matching
    aliases = load_aliases()
    matches = [g for g in entries if g.matches(terms)]
    # Also match by aliases, as a whole name or as a wildcard pattern
    for term in terms:
        for alias, accession in aliases.items():
            hit = fnmatch.fnmatch(alias.lower(), term.lower()) if is_glob(term) else term.lower() == alias.lower()
            if hit:
                for g in entries:
                    if g.accession == accession and g not in matches:
                        matches.append(g)
    if installed:
        matches = [g for g in matches if g.identifier in by_origin]

    query = " ".join(terms)
    if not matches:
        click.echo(f"No genome matches {query!r}")
        click.echo("Run 'leishref info' to list the catalog")
        raise SystemExit(1)

    plural = "es" if len(matches) > 1 else ""
    _console().print(f"[bold]{len(matches)}[/] match{plural} for [bold yellow]{escape(repr(query))}[/]\n")

    if long_form:
        import yaml

        for genome in matches:
            click.echo(yaml.safe_dump(genome.to_dict(), sort_keys=False, default_flow_style=False).rstrip())
            click.echo("")
        return

    console = _console()
    ordered = _by_organism(matches)
    # Size the two variable columns to what is actually being shown: a search for one
    # species should not be padded out to the width of the longest name in the catalog.
    id_width = min(max(len(g.identifier) for g in ordered), 38)
    organism_width = min(max(len(_organism(g)) for g in ordered), 44)

    for genome in ordered:
        organism = _organism(genome)
        year = (genome.release_date or "")[:4]
        level = (genome.assembly_level or "").replace("Complete Genome", "Complete")

        bases = genome.stats.get("num_bases")
        size = f"{bases / 1e6:.1f} Mb" if bases else ""
        scaffolds = genome.stats.get("num_scaffolds")
        count = f"{scaffolds} scaf" if scaffolds else ""

        # Scaffold N50 is the headline contiguity figure; contig N50 is in the record.
        n50 = genome.stats.get("scaffold_n50")
        contiguity = f"N50 {n50 / 1e6:.1f}M" if n50 and n50 >= 1e6 else (f"N50 {n50 / 1e3:.0f}k" if n50 else "")

        suffixes = []
        if genome.molecule_type:
            suffixes.append(genome.molecule_type)
        alias = get_catalog_alias(genome.accession or genome.identifier)
        if alias:
            suffixes.append(f"alias: {alias}")
        if genome.identifier in by_origin:
            suffixes.append(f"installed as {by_origin[genome.identifier]}")
        suffix = "  [" + ", ".join(suffixes) + "]" if suffixes else ""

        source = _source_label(genome)
        source_style = SOURCE_STYLES.get(source, "")
        console.print(
            f"  [bold cyan]{escape(genome.identifier):<{id_width}}[/]"
            f"  {escape(organism[:organism_width]):<{organism_width}}"
            f" [{source_style or 'default'}]{source:<9}[/] [dim]{year:<5}[/] {level:<11}"
            f" {size:>8} [dim]{count:>10} {contiguity:>9}[/][dim green]{escape(suffix)}[/]"
        )


@cli.command()
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--quick", is_flag=True, help="Check presence only, skip checksums")
def verify(local_dir, quick):
    """Check the local database against the checksums recorded with each genome.

    Examples:

    \b
      leishref verify
      leishref verify --quick
    """
    installed = local(Path(local_dir))
    ok, missing, mismatch = 0, [], []

    with click.progressbar(installed, label="Verifying", show_eta=True, show_pos=True) as bar:
        for genome in bar:
            for kind, path, recorded in genome.file_paths():
                if not path.exists():
                    missing.append((genome.identifier, path))
                elif quick or not recorded:
                    ok += 1
                elif md5_file(path) != recorded:
                    mismatch.append((genome.identifier, path))
                else:
                    ok += 1

    console = _console()
    console.print(f"Checked [bold]{len(installed)}[/] installed genomes")
    console.print(f"  ok:       [green]{ok}[/]")
    console.print(f"  missing:  [{'red' if missing else 'green'}]{len(missing)}[/]")
    console.print(f"  mismatch: [{'red' if mismatch else 'green'}]{len(mismatch)}[/]")

    errors = _console(err=True)
    for label, entries in (("MISSING", missing), ("CHECKSUM MISMATCH", mismatch)):
        if entries:
            errors.print(f"\n[bold red]{label}:[/]")
            for identifier, path in entries:
                errors.print(f"  [bold]{escape(identifier)}[/]: {escape(str(path))}")

    if missing or mismatch:
        raise SystemExit(1)


@cli.command("rename-sequences")
@click.argument("name")
@click.option(
    "--flavor",
    type=click.Choice(["chr", "number", "roman", "name"]),
    default="number",
    show_default=True,
    help="Naming scheme for renamed sequences",
)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
def rename_sequences_cmd(name, flavor, local_dir):
    """Rename sequences in a cached genome using chromosome database.

    NAME is the local alias of the genome to transform.

    Flavors:
    - chr: 'chromosome I', 'chromosome II', ...
    - number: '1', '2', '3', ... (default)
    - roman: 'I', 'II', 'III', ...
    - name: use names from chromosome database

    Examples:

    \b
      leishref rename-sequences Ld1S
      leishref rename-sequences Ld1S --flavor number
      leishref rename-sequences Ld1S --flavor roman
    """
    genome = _require(local(Path(local_dir)), name, "cached database")

    fasta_path = None
    for kind, path, _ in genome.file_paths():
        if kind == "fasta" and path.exists():
            fasta_path = path
            break

    if not fasta_path:
        click.echo(f"No FASTA file found for {name}", err=True)
        raise SystemExit(1)

    from leishref.chromosomes import load_chromosome_map, save_chromosome_map

    # Use accession or identifier as the chromosome map key
    chrom_key = genome.accession or genome.identifier

    click.echo(f"Renaming sequences in {fasta_path.name} ({flavor} flavor)...")
    renamed, name_map, error = rename_fasta_sequences(fasta_path, chrom_key, flavor, None)

    if error:
        click.echo(f"Warning: {error}", err=True)
        click.echo(f"Auto-detected {len(name_map)} sequences from FASTA file", err=True)

    # Write to new file with flavor suffix
    renamed_path = fasta_path.parent / f"{fasta_path.stem}.{flavor}{fasta_path.suffix}"
    renamed_path.write_text(renamed)
    click.echo(f"Wrote renamed sequences to {renamed_path.name}")

    # Create symlink in current directory with genome alias name
    link_name = Path.cwd() / f"{name}.{flavor}{fasta_path.suffix}"
    if link_name.exists() or link_name.is_symlink():
        link_name.unlink()
    link_name.symlink_to(renamed_path)
    click.echo(f"  {link_name.name} -> {renamed_path}")

    # Update chromosome_map.yaml with the mapping
    if name_map:
        chrom_map = load_chromosome_map()
        if chrom_key not in chrom_map:
            chrom_map[chrom_key] = []

        # Build mapping entries from chrom_info
        chrom_info = chrom_map.get(chrom_key, [])
        for i, info in enumerate(chrom_info, 1):
            old_name = info.get("accession", f"sequence_{i}")
            if old_name in name_map:
                info["new_name"] = name_map[old_name]

        save_chromosome_map(chrom_map)
        click.echo("Updated chromosome mapping in catalog/chromosome_map.yaml")


@cli.command("prune-scaffold")
@click.argument("name")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
def prune_scaffold_cmd(name, local_dir):
    """Remove unmapped contigs, keeping only chromosome sequences and kinetoplast.

    NAME is the local alias of the genome to prune.

    Requires genome accession and chromosome info in cached database.
    Kinetoplast sequences are preserved automatically.

    Examples:

    \b
      leishref prune-scaffold Ld1S
    """
    genome = _require(local(Path(local_dir)), name, "cached database")

    if not genome.accession:
        click.echo(f"Genome {name} has no accession; cannot look up chromosome info", err=True)
        raise SystemExit(1)

    chrom_info = get_chromosome_info(genome.accession)

    if not chrom_info:
        click.echo(f"No chromosome info found for {genome.accession}", err=True)
        click.echo("Populate chromosome database using 'leishref dev fetch-genome'", err=True)
        raise SystemExit(1)

    fasta_path = None
    for kind, path, _ in genome.file_paths():
        if kind == "fasta" and path.exists():
            fasta_path = path
            break

    if not fasta_path:
        click.echo(f"No FASTA file found for {name}", err=True)
        raise SystemExit(1)

    mapped_names = {info.get("accession") for info in chrom_info if info.get("accession")}
    click.echo(f"Pruning {fasta_path.name} ({len(mapped_names)} mapped + kinetoplast)...")
    pruned = prune_fasta(fasta_path, mapped_names)
    fasta_path.write_text(pruned)

    # Recompute stats and checksum
    new_checksum = md5_file(fasta_path)
    genome.checksums["fasta"] = new_checksum
    genome.stats = genome_stats(fasta_path)
    write_genome(genome.path, genome)

    click.echo(f"Pruned {fasta_path.name}")
    click.echo(f"  Sequences: {genome.stats.get('num_scaffolds', 'unknown')}")
    click.echo(f"  Checksum: {new_checksum}")


@cli.command()
@click.option(
    "--file",
    "accessions",
    type=click.Path(),
    help=f"Read from here instead of ./{ACCESSIONS_FILE}",
)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Download again even if already installed")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlinks")
@click.option("--dry-run", is_flag=True, help="List what would be downloaded and stop")
@click.option("--from-installed", is_flag=True, help="Write the file from what is already installed, then stop")
@click.option("--verbose", is_flag=True, help="Show each download in full instead of a progress bar")
@click.option("--parallel", type=int, default=1, show_default=True, help="Concurrent downloads")
def restore(accessions, local_dir, force, no_link, dry_run, from_installed, verbose, parallel):
    """Re-download every genome listed in accessions.txt in the current directory.

    'leishref install' records what it installed under which alias to accessions.txt,
    so a database can be rebuilt from that file alone - on another machine, or after
    cached genomes are cleared. Genomes already installed are left alone unless --force
    is given.

    Examples:

    \b
      leishref restore
      leishref restore --dry-run
      leishref restore --from-installed
      leishref restore --file ../other-project/accessions.txt
      leishref restore --verbose
      leishref restore --parallel 8
    """
    path = Path(accessions) if accessions else Path.cwd() / ACCESSIONS_FILE

    if from_installed:
        # A database built before this file existed can still describe itself: every
        # cached genome remembers the catalog entry it came from under provenance.
        written = 0
        for genome in _by_organism(local(Path(local_dir))):
            origin = genome.provenance.get("catalog_id") or genome.accession
            if not origin:
                click.echo(f"  no catalog origin recorded, skipping: {genome.identifier}", err=True)
                continue
            alias = genome.path.name  # Cached directory name is the alias
            _record_download(Path(local_dir), origin, alias)
            written += 1
        click.echo(f"Recorded {written} genome{'s' if written != 1 else ''} in {path}")
        return
    if not path.exists():
        click.echo(f"No accessions file at {path}", err=True)
        click.echo("It is written by 'leishref install'; nothing to restore yet.", err=True)
        raise SystemExit(1)

    pairs = _read_accessions(path)
    if not pairs:
        click.echo(f"{path} lists no genomes")
        raise SystemExit(1)

    console = _console()
    console.print(f"[bold]{len(pairs)}[/] genome{'s' if len(pairs) > 1 else ''} listed in [cyan]{escape(str(path))}[/]")

    if dry_run:
        for name, alias in pairs:
            state = "installed" if (Path(local_dir) / alias / "metadata.yaml").exists() else "missing"
            console.print(f"  [bold cyan]{escape(alias):<24}[/] {escape(name):<34} [dim]{state}[/]")
        return

    failed = []

    if parallel > 1:
        entries = catalog()
        genome_pairs = []
        for name, alias in pairs:
            genome = find(entries, name)
            if genome is None:
                click.echo(f"failed: {alias} <- {name} (not in catalog)", err=True)
                failed.append(alias)
                continue
            genome_pairs.append((genome, alias))
        failed.extend(_install_many_parallel(genome_pairs, Path(local_dir), force, no_link, parallel, click.echo))
    else:
        # Restoring a whole database is a long, mostly uninteresting wait, so the
        # per-genome chatter of 'download' is swallowed and only a progress bar is
        # shown. What was swallowed is printed for the genomes that failed, where it
        # is the diagnosis. disable=None leaves the bar off when stderr is not a
        # terminal, so a piped or redirected restore stays clean.
        bar = tqdm(pairs, unit="genome", disable=True if verbose else None, dynamic_ncols=True)
        for name, alias in bar:
            if not verbose:
                bar.set_description_str(alias[:28], refresh=True)
            else:
                console.print(f"\n[bold]{escape(alias)}[/] <- {escape(name)}")

            captured = io.StringIO()
            try:
                with contextlib.ExitStack() as stack:
                    if not verbose:
                        stack.enter_context(contextlib.redirect_stdout(captured))
                        stack.enter_context(contextlib.redirect_stderr(captured))
                    click.get_current_context().invoke(
                        install,
                        name=name,
                        alias=alias,
                        local_dir=local_dir,
                        force=force,
                        no_link=no_link,
                    )
            except SystemExit as exc:
                # One unavailable genome should not abandon the rest of the database.
                if exc.code:
                    failed.append(alias)
                    message = captured.getvalue().strip()
                    tqdm.write(f"failed: {alias} <- {name}")
                    if message:
                        tqdm.write(textwrap.indent(message, "  "))
        bar.close()

    console.print(f"Restored [bold]{len(pairs) - len(failed)}[/]/{len(pairs)} into [cyan]{escape(str(local_dir))}[/]")
    if failed:
        _console(err=True).print(f"[bold red]{len(failed)} failed:[/] {escape(', '.join(failed))}")
        raise SystemExit(1)


def _ncbi_install_alias(genome_for_alias) -> str:
    """Catalog alias for an NCBI accession (Ld1S, LdBPK), or a sanitized suggested one."""
    alias = get_catalog_alias(genome_for_alias.accession) if genome_for_alias.accession else None
    if not alias:
        alias = suggest_alias(genome_for_alias).replace("/", "_")
    return alias


@cli.command("install-ncbi")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Install again even if already installed")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlinks")
@click.option("--verbose", is_flag=True, help="Show each install details instead of progress bar")
@click.option("--parallel", type=int, default=1, show_default=True, help="Concurrent downloads")
def install_ncbi(local_dir, force, no_link, verbose, parallel):
    """Install all NCBI entries from the catalog.

    Examples:

    \b
      leishref install-ncbi
      leishref install-ncbi --force
      leishref install-ncbi --parallel 8
    """
    entries = catalog()
    ncbi_genomes = [g for g in entries if g.source == "NCBI" and g.accession]

    if not ncbi_genomes:
        click.echo("No NCBI genomes found in catalog")
        return

    click.echo(f"Installing {len(ncbi_genomes)} NCBI genomes...")

    if parallel > 1:
        pairs = [(g, _ncbi_install_alias(g)) for g in ncbi_genomes]
        failed = _install_many_parallel(pairs, Path(local_dir), force, no_link, parallel, click.echo)
    else:
        bar = tqdm(ncbi_genomes, unit="genome", disable=True if verbose else None, dynamic_ncols=True)
        failed = []

        for genome in bar:
            # Prefer catalog alias (Ld1S, LdBPK), fall back to suggest_alias
            alias = _ncbi_install_alias(genome)
            bar.set_description_str(alias[:28], refresh=True)

            captured = io.StringIO()
            try:
                with contextlib.ExitStack() as stack:
                    if not verbose:
                        stack.enter_context(contextlib.redirect_stdout(captured))
                        stack.enter_context(contextlib.redirect_stderr(captured))
                    click.get_current_context().invoke(
                        install,
                        name=genome.accession,
                        alias=alias,
                        local_dir=local_dir,
                        force=force,
                        no_link=no_link,
                    )
            except SystemExit as exc:
                if exc.code:
                    failed.append(alias)
                    if verbose:
                        click.echo(f"  Failed: {alias}", err=True)

    if failed:
        click.echo(f"\nFailed: {len(failed)}/{len(ncbi_genomes)}", err=True)
        for alias in failed:
            click.echo(f"  {alias}", err=True)
        raise SystemExit(1)
    else:
        click.echo(f"\nDownloaded {len(ncbi_genomes)} NCBI genomes")


@cli.command("install-ncbi-refseq")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Install again even if already installed")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlinks")
@click.option("--verbose", is_flag=True, help="Show each install details instead of progress bar")
@click.option("--parallel", type=int, default=1, show_default=True, help="Concurrent downloads")
def install_ncbi_refseq(local_dir, force, no_link, verbose, parallel):
    """Install all RefSeq (GCF) NCBI entries from the catalog.

    Examples:

    \b
      leishref install-ncbi-refseq
      leishref install-ncbi-refseq --force
      leishref install-ncbi-refseq --parallel 8
    """
    entries = catalog()
    ncbi_genomes = [g for g in entries if g.source == "NCBI" and g.accession and g.accession.startswith("GCF_")]

    if not ncbi_genomes:
        click.echo("No RefSeq (GCF) genomes found in catalog")
        return

    click.echo(f"Installing {len(ncbi_genomes)} RefSeq genomes...")

    if parallel > 1:
        pairs = [(g, _ncbi_install_alias(g)) for g in ncbi_genomes]
        failed = _install_many_parallel(pairs, Path(local_dir), force, no_link, parallel, click.echo)
    else:
        bar = tqdm(ncbi_genomes, unit="genome", disable=True if verbose else None, dynamic_ncols=True)
        failed = []

        for genome in bar:
            alias = _ncbi_install_alias(genome)
            bar.set_description_str(alias[:28], refresh=True)

            captured = io.StringIO()
            try:
                with contextlib.ExitStack() as stack:
                    if not verbose:
                        stack.enter_context(contextlib.redirect_stdout(captured))
                        stack.enter_context(contextlib.redirect_stderr(captured))
                    click.get_current_context().invoke(
                        install,
                        name=genome.accession,
                        alias=alias,
                        local_dir=local_dir,
                        force=force,
                        no_link=no_link,
                    )
            except SystemExit as exc:
                if exc.code:
                    failed.append(alias)
                    if verbose:
                        click.echo(f"  Failed: {alias}", err=True)

    if failed:
        click.echo(f"\nFailed: {len(failed)}/{len(ncbi_genomes)}", err=True)
        for alias in failed:
            click.echo(f"  {alias}", err=True)
        raise SystemExit(1)
    else:
        click.echo(f"\nDownloaded {len(ncbi_genomes)} RefSeq genomes")


@cli.command()
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--basedir", type=click.Path(), default=".", help="Where to create the links")
def link(local_dir, basedir):
    """Refresh the alias-named symlinks for everything installed locally.

    Examples:

    \b
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


@cli.command("plot-sizes")
@click.option("--catalog-dir", type=click.Path(), help="Catalog directory")
@click.option("--output", type=click.Path(), help="Save plot to this file")
@click.option("--species", multiple=True, help="Filter by species (can repeat)")
@click.option("--include-kinetoplast", is_flag=True, help="Include kinetoplast-only genomes")
def plot_sizes(catalog_dir, output, species, include_kinetoplast):
    """Plot genome sizes by species.

    Kinetoplast-only entries are excluded by default (they're outliers).
    Use --include-kinetoplast to show all entries.

    Examples:

    \b
      leishref plot-sizes
      leishref plot-sizes --output sizes.png
      leishref plot-sizes --species donovani --species major
      leishref plot-sizes --include-kinetoplast
    """
    try:
        out = plot_genome_sizes(
            Path(catalog_dir) if catalog_dir else None,
            Path(output) if output else None,
            list(species) if species else None,
            include_kinetoplast=include_kinetoplast,
        )
        click.echo(f"Saved plot to {out}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("plot-stats")
@click.option("--catalog-dir", type=click.Path(), help="Catalog directory")
@click.option("--output", type=click.Path(), help="Save plot to this file")
def plot_stats(catalog_dir, output):
    """Plot genome statistics: genome size, scaffold count, contig count, scaffold N50.

    Examples:

    \b
      leishref plot-stats
      leishref plot-stats --output stats.png
    """
    try:
        out = plot_genome_stats(
            Path(catalog_dir) if catalog_dir else None,
            Path(output) if output else None,
        )
        click.echo(f"Saved plot to {out}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("plot-chromosome-histogram")
@click.option("--catalog-dir", type=click.Path(), help="Catalog directory")
@click.option("--output", type=click.Path(), help="Save plot to this file")
@click.option("--species", multiple=True, help="Filter by species (can repeat)")
def plot_chromosome_histogram(catalog_dir, output, species):
    """Plot chromosome/sequence length histogram from available local FASTA files.

    Examples:

    \b
      leishref plot-chromosome-histogram
      leishref plot-chromosome-histogram --output chromosome_lengths.png
      leishref plot-chromosome-histogram --species tropica
    """
    try:
        out = plot_chromosome_length_histogram(
            Path(catalog_dir) if catalog_dir else None,
            Path(output) if output else None,
            list(species) if species else None,
        )
        click.echo(f"Saved plot to {out}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("plot-histogram")
@click.option("--catalog-dir", type=click.Path(), help="Catalog directory")
@click.option("--output", type=click.Path(), help="Save plot to this file")
@click.option("--include-kinetoplast", is_flag=True, help="Include kinetoplast-only genomes")
def plot_histogram(catalog_dir, output, include_kinetoplast):
    """Plot histogram of genome sizes.

    Kinetoplast-only entries are excluded by default (they're outliers).
    Use --include-kinetoplast to show all entries.

    Examples:

    \b
      leishref plot-histogram
      leishref plot-histogram --output histogram.png
      leishref plot-histogram --include-kinetoplast
    """
    try:
        out = plot_genome_size_histogram(
            Path(catalog_dir) if catalog_dir else None,
            Path(output) if output else None,
            include_kinetoplast=include_kinetoplast,
        )
        click.echo(f"Saved plot to {out}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


def _resolve_symlink_targets(pattern: str, basedir: Path = Path(".")) -> list[tuple[str, Path]]:
    """Match files by pattern, resolve symlinks to actual files.

    Returns list of (arcname, resolved_path) tuples.
    arcname is just the symlink name (for flat archive from current dir).
    """
    from glob import glob

    basedir = Path(basedir)
    results = []
    matches = glob(pattern, root_dir=basedir)

    if not matches:
        return []

    for filename in sorted(matches):
        filepath = basedir / filename
        if filepath.is_symlink():
            target = filepath.resolve()
            results.append((filepath.name, target))
        elif filepath.is_file():
            results.append((filepath.name, filepath))

    return results


@cli.command()
@click.argument("patterns", nargs=-1, required=True)
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--basedir", type=click.Path(), default=".", help="Directory to search for symlinks")
@click.option("--output", "-o", type=click.Path(), help="Output tarball path (default: bundle.tar.gz)")
def bundle(patterns, local_dir, basedir, output):
    """Pack genomes into a tarball: from symlinks or by genome name.

    Supports two modes:

    1. FILE PATTERNS (symlinks in current dir):
       leishref bundle '*.fna'
       leishref bundle 'Ld*.fna' 'Ltrop*.gff'
       Resolves symlinks to actual files in ~/.config/leishref

    2. GENOME NAMES (from database):
       leishref bundle Ld1S LdBPK
       leishref bundle 'Ld*'
       Uses genome identifiers with wildcard support

    Creates a .tar.gz with all files, preserving relative paths. Useful for
    offline sharing or backup.

    Examples:

    \b
      leishref bundle '*.fna'
      leishref bundle 'Ld*.fna' -o ld-genomes.tar.gz
      leishref bundle Ld1S LdBPK
      leishref bundle 'Ld*' -o ld-all.tar.gz
    """
    basedir = Path(basedir)
    installed = local(Path(local_dir))

    files_to_bundle = []

    for pattern in patterns:
        symlink_matches = _resolve_symlink_targets(pattern, basedir)

        if symlink_matches:
            for linkname, target in symlink_matches:
                files_to_bundle.append((linkname, target))
        else:
            if is_glob(pattern):
                matches = [g for g in installed if fnmatch.fnmatch(g.identifier.lower(), pattern.lower())]
                if not matches:
                    click.echo(f"No match for '{pattern}' (tried symlinks and genomes)", err=True)
                    raise SystemExit(1)
                for genome in matches:
                    for kind, path, _ in genome.file_paths():
                        if path.exists():
                            arcname = f"{genome.identifier}/{path.name}"
                            files_to_bundle.append((arcname, path))
            else:
                genome = find(installed, pattern)
                if genome is None:
                    click.echo(f"Not found: {pattern} (symlink or genome name)", err=True)
                    raise SystemExit(1)
                for kind, path, _ in genome.file_paths():
                    if path.exists():
                        arcname = f"{genome.identifier}/{path.name}"
                        files_to_bundle.append((arcname, path))

    if not files_to_bundle:
        click.echo("No files to bundle", err=True)
        raise SystemExit(1)

    if not output:
        output = "bundle.tar.gz"

    output_path = Path(output)
    click.echo(f"Bundling {len(files_to_bundle)} file{'s' if len(files_to_bundle) != 1 else ''} into {output_path}")

    with tarfile.open(output_path, "w:gz") as tar:
        for arcname, filepath in files_to_bundle:
            click.echo(f"  {arcname}")
            tar.add(filepath, arcname=arcname)

    click.echo(f"\nBundled to {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Nested dict to dot-separated flat dict, for tabular formats."""
    items = {}
    for key, value in d.items():
        flat_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_dict(value, flat_key))
        else:
            items[flat_key] = value
    return items


def _records_to_tsv(records: list) -> str:
    """Flatten records and render as TSV, column union across all rows."""
    import csv
    import io

    flattened = [_flatten_dict(r) for r in records]
    columns = []
    seen = set()
    for row in flattened:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(flattened)
    return buf.getvalue()


@cli.command()
@click.option("--catalog-dir", type=click.Path(), help="Catalog directory")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option(
    "--source",
    type=click.Choice(["catalog", "local", "both"]),
    default="catalog",
    show_default=True,
    help="Which genomes to export",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "yaml", "tsv"]),
    default="json",
    show_default=True,
    help="Output format",
)
@click.option("--output", "-o", type=click.Path(), help="Write to file instead of stdout")
def export(catalog_dir, local_dir, source, fmt, output):
    """Export genome metadata as JSON, YAML, or TSV.

    Exports the catalog by default; pass --source local or --source both to include
    the cached database. TSV flattens nested fields with dot notation (e.g.
    stats.num_scaffolds), with a column union across all exported genomes.

    Examples:

    \b
      leishref export --format json
      leishref export --format tsv -o catalog.tsv
      leishref export --source both --format yaml -o everything.yaml
    """
    cat_root = Path(catalog_dir) if catalog_dir else None

    genomes = []
    if source in ("catalog", "both"):
        genomes.extend(catalog(cat_root))
    if source in ("local", "both"):
        genomes.extend(local(Path(local_dir)))

    records = [g.to_dict() for g in genomes]

    if fmt == "json":
        import json

        text = json.dumps(records, indent=2, default=str)
    elif fmt == "yaml":
        import yaml

        text = yaml.safe_dump(records, sort_keys=False, default_flow_style=False)
    else:
        text = _records_to_tsv(records)

    if output:
        Path(output).write_text(text)
        click.echo(f"Exported {len(records)} genome{'s' if len(records) != 1 else ''} to {output}")
    else:
        click.echo(text)


# ------------------------------------------------------------------------ dev commands


@dev.command("fetch-genome")
@click.argument("accession")
@click.option("--alias", help="Also install into the local database under this name")
@click.option("--species", help="Override the species reported by NCBI")
@click.option("--strain", help="Override the strain reported by NCBI")
@click.option(
    "--molecule-type",
    help="What this actually is when it isn't a nuclear assembly, e.g. 'kinetoplast,maxicircle'",
)
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Replace an existing catalog entry")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def fetch_genome(accession, alias, species, strain, molecule_type, catalog_dir, local_dir, force, no_link):
    """Add an NCBI genome assembly to the catalog.

    Downloads the assembly to record its checksums and statistics. Pass --alias to keep
    the files in the local database rather than discarding them.

    NCBI's own assembly_level doesn't flag a lone kinetoplast/maxicircle sequence
    submitted as a "genome assembly" - it still comes back as e.g. "Chromosome" - so
    pass --molecule-type by hand when you know that's what it actually is; otherwise
    it won't turn up in `leishref search kinetoplast`.

    Examples:

    \b
      leishref dev fetch-genome GCA_000410715.1
      leishref dev fetch-genome GCA_000410715.1 --alias Ltrop.L590
      leishref dev fetch-genome GCA_902369315.1 --molecule-type kinetoplast,maxicircle
    """
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    entry = root / "ncbi" / accession
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

        genome = Genome(
            identifier=accession,
            source="NCBI",
            accession=accession,
            taxon_id=meta.get("taxon_id"),
            species=species or species_from_organism(meta.get("organism_name")) or None,
            strain=strain or meta.get("strain"),
            assembly_name=meta.get("assembly_name"),
            assembly_level=meta.get("assembly_level"),
            molecule_type=molecule_type,
            release_date=meta.get("release_date"),
            files={k: v.name for k, v in (("fasta", fasta), ("gff", gff)) if v},
            checksums={k: md5_file(v) for k, v in (("fasta", fasta), ("gff", gff)) if v},
            stats=genome_stats(fasta),
            provenance={
                k: v
                for k, v in (
                    ("bioproject", meta.get("bioproject")),
                    ("biosample", meta.get("biosample")),
                    ("sequencing_technology", meta.get("sequencing_technology")),
                    ("assembler", meta.get("assembler")),
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


@dev.command("fetch-nucleotide")
@click.argument("accession")
@click.option("--alias", help="Also install into the local database under this name")
@click.option("--species", help="Override the organism reported by NCBI")
@click.option("--strain", help="Override the strain reported by NCBI")
@click.option(
    "--molecule-type",
    default="kinetoplast",
    show_default=True,
    help="What this is, e.g. 'kinetoplast,maxicircle'. Pass '' to leave unset.",
)
@click.option("--email", help="Contact email for NCBI EUtils (recommended; avoids rate-limit warnings)")
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--force", is_flag=True, help="Replace an existing catalog entry")
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def fetch_nucleotide(accession, alias, species, strain, molecule_type, email, catalog_dir, local_dir, force, no_link):
    """Add a standalone NCBI nucleotide (nuccore) record to the catalog.

    For a single sequence that isn't part of a GCA/GCF assembly - e.g. a lone
    kinetoplast or maxicircle deposited on its own. Fetched via NCBI EUtils
    (bioservices), not the `datasets` CLI used for assemblies.

    A standalone nuccore record is a kinetoplast/maxicircle far more often than
    anything else, so --molecule-type defaults to "kinetoplast" here (unlike
    fetch-genome, where it defaults unset); override it if this one is different.

    Examples:

    \b
      leishref dev fetch-nucleotide BK010877.1
      leishref dev fetch-nucleotide BK010877.1 --alias LiJPCM5.kinetoplast
      leishref dev fetch-nucleotide BK010877.1 --molecule-type kinetoplast,maxicircle
    """
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    entry = root / "ncbi_nucleotide" / accession
    if (entry / "metadata.yaml").exists() and not force:
        click.echo(f"Already in the catalog: {entry}", err=True)
        click.echo("Use --force to replace it", err=True)
        raise SystemExit(1)

    click.echo(f"Fetching {accession} from NCBI nuccore...")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fasta = fetch_nucleotide_fasta(accession, Path(tmp), email=email)
            meta = fetch_nucleotide_metadata(accession, email=email)
        except NuccoreError as exc:
            click.echo(str(exc), err=True)
            raise SystemExit(1)

        genome = Genome(
            identifier=accession,
            source="NCBI-Nucleotide",
            accession=accession,
            taxon_id=meta.get("taxon_id"),
            species=species or meta.get("organism"),
            strain=strain or meta.get("strain"),
            molecule_type=molecule_type or None,
            release_date=meta.get("release_date"),
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
            stats=genome_stats(fasta),
            notes=meta.get("title"),
            date_added=today_iso(),
        )

        write_genome(entry, genome)
        click.echo(f"Catalog entry: {entry}")

        if alias:
            installed = _install(genome, alias, [fasta], Path(local_dir))
            click.echo(f"Installed into {installed}")
            _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


@dev.command()
@click.argument("fasta", type=click.Path(exists=True))
@click.argument("gff", type=click.Path(exists=True), required=False)
@click.option("--alias", required=True, help="Name for this genome, in the catalog and locally")
@click.option("--species", help="Species name")
@click.option("--strain", help="Strain name")
@click.option("--technology", help="Sequencing technology, e.g. 'PacBio RS II'")
@click.option("--assembler", help="Assembler used, e.g. Flye")
@click.option(
    "--molecule-type",
    help="What this actually is when it isn't a nuclear assembly, e.g. 'kinetoplast,maxicircle'",
)
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def add(fasta, gff, alias, species, strain, technology, assembler, molecule_type, catalog_dir, local_dir, no_link):
    """Add a local assembly to the catalog and install it locally.

    Examples:

    \b
      leishref dev add assembly.fa --alias Ltrop.flye --species "Leishmania tropica"
      leishref dev add assembly.fa assembly.gff --alias Ltrop.flye
      leishref dev add kdna.fa --alias Lgu.kinetoplast --molecule-type kinetoplast,maxicircle
    """
    fasta, gff = Path(fasta), Path(gff) if gff else None
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR

    genome = Genome(
        identifier=alias,
        source="Local",
        species=species,
        strain=strain,
        molecule_type=molecule_type,
        files={k: v.name for k, v in (("fasta", fasta), ("gff", gff)) if v},
        checksums={k: md5_file(v) for k, v in (("fasta", fasta), ("gff", gff)) if v},
        stats=genome_stats(fasta),
        provenance={k: v for k, v in (("sequencing_technology", technology), ("assembler", assembler)) if v},
        date_added=today_iso(),
    )

    entry = catalog_entry_dir(root, genome)
    write_genome(entry, genome)
    click.echo(f"Catalog entry: {entry}")

    installed = _install(genome, alias, [fasta, gff], Path(local_dir))
    click.echo(f"Installed into {installed}")
    _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


@dev.command()
@click.option("--query", required=True, help="Assembly to scaffold: a FASTA file, catalog id or local alias")
@click.option("--reference", required=True, help="Reference genome: catalog id or local alias")
@click.option(
    "--alias", help="Name for the resulting scaffold (auto-generated as <query>.scaffold.<reference> if omitted)"
)
@click.option("--clean", is_flag=True, help="Keep only chr-anchored contigs plus kinetoplast")
@click.option("--catalog-dir", type=click.Path(), help="Write the entry here instead")
@click.option("--local-dir", type=click.Path(), default=str(LOCAL_DIR), show_default=True)
@click.option("--no-link", is_flag=True, help="Skip the alias-named symlink")
def scaffold(query, reference, alias, clean, catalog_dir, local_dir, no_link):
    """Scaffold an assembly against a reference with ragtag.

    Both query and reference must be installed catalog genomes. The result describes
    the query: scaffolding L. tropica onto L. donovani yields an L. tropica assembly,
    with L. donovani appearing only in the provenance. Species and strain are taken
    from the query metadata.

    The scaffold is named as <query_alias>.scaffold.<reference_alias> by default; pass
    --alias to override with a custom name.

    Examples:

    \b
      leishref dev scaffold --query Ltrop.ncbi.L590 --reference Ld1S
      leishref dev scaffold --query Ltrop.ncbi.L590 --reference Ld1S --alias custom.name
      leishref dev scaffold --query Ltrop.ncbi.L590 --reference Ld1S --clean
    """
    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    local_root = Path(local_dir)
    cat_root = Path(catalog_dir) if catalog_dir else None

    query_fasta, query_genome = _resolve_assembly(query, local_root, cat_root, "--query")
    ref_fasta, ref = _resolve_assembly(reference, local_root, cat_root, "--reference")
    query = query_fasta

    if query_genome is None:
        click.echo("--query must be an installed catalog genome (not a bare FASTA file).", err=True)
        raise SystemExit(1)
    if ref is None:
        click.echo("--reference must be an installed catalog genome.", err=True)
        raise SystemExit(1)

    if not alias:
        query_alias = _genome_alias(query_genome, cat_root)
        ref_alias = _genome_alias(ref, cat_root)
        alias = f"{query_alias}.scaffold.{ref_alias}"
        click.echo(f"Auto-generated scaffold name: {alias}")

    species = query_genome.species
    strain = query_genome.strain
    if not species:
        click.echo(f"Cannot determine species from query {query_genome.identifier}.", err=True)
        raise SystemExit(1)

    click.echo(f"Scaffolding {query.name} onto {reference}...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        scaffold_fasta, scaffold_agp = run_scaffold(ref_fasta, query, tmp)

        result = tmp / f"{alias}.fna"
        if clean:
            result.write_text(clean_scaffolded_fasta(scaffold_fasta, scaffold_agp))
        else:
            shutil.copy(scaffold_fasta, result)
        agp = tmp / f"{alias}.agp"
        shutil.copy(scaffold_agp, agp)

        genome = Genome(
            identifier=alias,
            source="Leishref scaffold",
            species=species,
            strain=strain,
            assembly_level="Scaffold",
            files={"fasta": result.name},
            checksums={"fasta": md5_file(result)},
            stats=genome_stats(result),
            provenance={"agp_filename": agp.name},
            scaffold={
                "query": _parent_record(query_fasta, query_genome),
                "reference": _parent_record(ref_fasta, ref),
                "tool": "RagTag",
                "tool_version": ragtag_version(),
                "cleaned": True if clean else None,
            },
            date_added=today_iso(),
        )
        genome.scaffold = {k: v for k, v in genome.scaffold.items() if v is not None}

        entry = catalog_entry_dir(root, genome)
        write_genome(entry, genome)
        click.echo(f"Catalog entry: {entry}")

        installed = _install(genome, alias, [result, agp], local_root, move=True)

    click.echo(f"Installed into {installed}")
    _link(alias, [p for _, p, _ in read_genome(installed).file_paths() if p.exists()], no_link)


def _zenodo_description(genome) -> str:
    """Build rich description for Zenodo deposit with HTML formatting."""
    lines = [
        "<p>Leishmania genome assembly from the leishref initiative.</p>",
        '<p>Repository: <a href="https://github.com/cokelaer/leishref">https://github.com/cokelaer/leishref</a></p>',
    ]

    if genome.source == "Leishref scaffold":
        scaf = genome.scaffold or {}
        query = scaf.get("query", {})
        ref = scaf.get("reference", {})
        num_scaffolds = genome.stats.get("num_scaffolds", "unknown")
        num_contigs = genome.stats.get("num_contigs", "unknown")

        lines.append(
            f"<p><strong>Scaffolded assembly:</strong><br/>"
            f"Query: {query.get('name', 'unknown')} ({query.get('species', 'unknown')})<br/>"
            f"Reference: {ref.get('name', 'unknown')} ({ref.get('species', 'unknown')})<br/>"
            f"Tool: {scaf.get('tool', 'unknown')} {scaf.get('tool_version', '')}".strip() + "<br/>"
            f"Result: {num_scaffolds} scaffolds, {num_contigs} contigs</p>"
        )
    else:
        lines.append(
            f"<p>"
            f"Accession: {genome.accession or 'N/A'}<br/>"
            f"Species: {genome.species or 'unknown'}<br/>"
            f"Strain: {genome.strain or 'unknown'}<br/>"
            f"Assembly level: {genome.assembly_level or 'unknown'}"
        )
        if genome.stats:
            lines[-1] += f"<br/>Sequences: {genome.stats.get('num_scaffolds', 'unknown')} scaffolds"
        lines[-1] += "</p>"

    lines.append(
        "<p><strong>Citation:</strong> If using this assembly, please cite the leishref project:<br/>"
        '<a href="https://github.com/cokelaer/leishref">https://github.com/cokelaer/leishref</a></p>'
    )

    return "\n".join(lines)


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

    \b
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

    author = click.prompt("Author name")
    try:
        title = f"Leishmania genome: {genome.identifier}"
        description = _zenodo_description(genome)
        creators = ["LeishRef"]
        if author:
            creators.append(author)
        deposition = create_deposition(title, description, creators, sandbox=sandbox)
        click.echo(f"Created deposition {deposition['id']}")

        for path in payload:
            click.echo(f"Uploading {path.name}...")
            upload_file(deposition["id"], path, sandbox=sandbox)

        keywords = ["leishmania", "genome", "assembly", "leishref"]
        if genome.source == "Leishref scaffold":
            keywords.append("scaffold")

        update_metadata(
            deposition["id"],
            {
                "metadata": {
                    "title": deposition["metadata"]["title"],
                    "description": description,
                    "creators": deposition["metadata"]["creators"],
                    "version": version or "v1.0",
                    "keywords": keywords,
                    "upload_type": "dataset",
                    "related_identifiers": [
                        {
                            "identifier": "https://github.com/cokelaer/leishref",
                            "relation": "isPartOf",
                        }
                    ],
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
    genome.source = "Zenodo"
    if version:
        genome.release_version = version
    write_genome(genome.path, genome)

    root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    origin = genome.provenance.get("catalog_id") or genome.identifier
    shipped = find(catalog(Path(catalog_dir) if catalog_dir else None), origin)
    entry = shipped.path if shipped else catalog_entry_dir(root, genome)
    if (entry / "metadata.yaml").exists():
        shipped = read_genome(entry)
        shipped.provenance["zenodo_doi"] = doi
        shipped.source = "Zenodo"
        write_genome(entry, shipped)
        click.echo(f"Recorded DOI in {entry}")


@dev.command()
@click.argument("identifier")
@click.option("--catalog-dir", type=click.Path(), help="Remove from here instead of shipped catalog")
@click.option("--force", is_flag=True, help="Don't ask for confirmation")
def remove(identifier, catalog_dir, force):
    """Remove a genome entry from the catalog.

    IDENTIFIER is the genome identifier or accession to remove.

    Examples:

    \b
      leishref dev remove LtrL590.scaffold.Ld1S
      leishref dev remove GCA_000227135.2 --force
    """
    cat_root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    genome = _require(catalog(cat_root), identifier, "catalog", cat_root)

    if not force:
        click.echo(f"Remove {genome.identifier}?")
        if not click.confirm("Continue"):
            raise SystemExit(0)

    entry_path = genome.path
    click.echo(f"Removing {entry_path}...")
    import shutil

    shutil.rmtree(entry_path, ignore_errors=False)
    click.echo(f"Removed {entry_path}")


@dev.command("check-aliases")
@click.option("--catalog-dir", type=click.Path(), help="Check this catalog instead")
def check_aliases(catalog_dir):
    """Check for duplicate accessions and aliases.

    Examples:

    \b
      leishref dev check-aliases
    """
    from collections import defaultdict

    # Check catalog accessions
    cat_root = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    entries = catalog(cat_root)

    accessions = defaultdict(list)
    for g in entries:
        if g.accession:
            accessions[g.accession].append(g.identifier)

    dups = {acc: ids for acc, ids in accessions.items() if len(ids) > 1}

    if dups:
        click.echo("Duplicate accessions in catalog:", err=True)
        for acc, ids in sorted(dups.items()):
            click.echo(f"  {acc}: {', '.join(ids)}", err=True)
        raise SystemExit(1)
    else:
        click.echo("✓ No duplicate accessions in catalog")

    # Check aliases
    aliases_file = CATALOG_DIR / "aliases.txt"
    if aliases_file.exists():
        aliases = defaultdict(list)
        for line in aliases_file.read_text().split("\n"):
            if line and not line.startswith("#"):
                parts = line.split("\t")
                if len(parts) == 2:
                    accession, alias = parts
                    aliases[alias].append(accession)

        dups_aliases = {alias: accs for alias, accs in aliases.items() if len(accs) > 1}
        if dups_aliases:
            click.echo("Duplicate aliases:", err=True)
            for alias, accs in sorted(dups_aliases.items()):
                click.echo(f"  {alias}: {', '.join(accs)}", err=True)
            raise SystemExit(1)
        else:
            click.echo(f"✓ No duplicate aliases ({len(aliases)} total)")

    click.echo("✓ All checks passed")


if __name__ == "__main__":
    cli()
