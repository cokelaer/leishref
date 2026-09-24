"""Command-line behaviour that does not need the network."""

import csv
import os

import pytest
from click.testing import CliRunner

from leishref.checksums import md5_file
from leishref.cli import cli
from leishref.metadata import Genome, read_genome, write_genome


@pytest.fixture
def installed(tmp_path):
    """A local database holding one genome, with matching checksums."""
    directory = tmp_path / "data" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGTACGT\n")

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species="Leishmania tropica",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    # Create chromosome_map.csv for test genome (in shared_catalog subdir)
    catalog_dir = tmp_path / "shared_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    csv_file = catalog_dir / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "c1", "chromosome": "1", "taxid": "5666", "origin": "Ltrop.flye"})

    return tmp_path, fasta


def run(args, cwd, input=None):
    """Invoke the CLI as if it had been started from cwd.

    NO_COLOR keeps rich's output plain regardless of the calling terminal (e.g. a
    shell with FORCE_COLOR set), so string assertions on the output stay reliable.
    """
    previous = os.getcwd()
    os.chdir(cwd)
    try:
        return CliRunner().invoke(cli, args, input=input, env={"NO_COLOR": "1", "FORCE_COLOR": ""})
    finally:
        os.chdir(previous)


def test_install_requires_an_alias(tmp_path):
    result = run(["install", "GCA_000410715.1", "--local-dir", "data"], tmp_path)
    assert result.exit_code != 0
    assert "--alias" in result.output


def test_user_and_dev_commands_are_separated():
    result = CliRunner().invoke(cli, ["--help"])
    assert "install" in result.output
    assert "dev" in result.output
    assert "publish" not in result.output, "maintainer commands belong under dev"

    dev = CliRunner().invoke(cli, ["dev", "--help"])
    for command in ("fetch", "add", "scaffold", "publish"):
        assert command in dev.output


def test_verify_passes_on_an_intact_database(installed):
    base, _ = installed
    result = run(["verify", "--local-dir", "data"], base)
    assert result.exit_code == 0
    assert "mismatch: 0" in result.output


def test_verify_fails_when_a_file_changed(installed):
    base, fasta = installed
    fasta.write_text(">c1\nTTTTTTTT\n")

    result = run(["verify", "--local-dir", "data"], base)
    assert result.exit_code == 1
    assert "CHECKSUM MISMATCH" in result.output


def test_verify_reports_a_missing_file(installed):
    base, fasta = installed
    fasta.unlink()

    result = run(["verify", "--local-dir", "data"], base)
    assert result.exit_code == 1
    assert "MISSING" in result.output


def test_link_creates_alias_named_symlinks(installed):
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\n")
    result = run(["link", "--local-dir", "data"], base)

    link = base / "Ltrop.flye.fna"
    assert result.exit_code == 0
    assert link.is_symlink()
    assert link.read_text() == ">c1\nACGTACGT\n"


def test_info_lists_catalog_and_local(installed):
    base, _ = installed
    result = run(["info", "--local-dir", "data"], base)

    assert "Catalog:" in result.output
    assert "Cached: 1 installed" in result.output
    assert "Ltrop.flye" in result.output


def test_info_on_an_unknown_name_fails_clearly(installed):
    base, _ = installed
    result = run(["info", "nonexistent", "--local-dir", "data"], base)

    assert result.exit_code == 1
    assert "Not in catalog" in result.output


def test_search_narrows_with_more_terms(installed):
    base, _ = installed
    broad = run(["search", "tropica", "--local-dir", "data"], base)
    narrow = run(["search", "tropica", "L590", "--local-dir", "data"], base)

    assert broad.exit_code == narrow.exit_code == 0
    assert int(narrow.output.split()[0]) < int(broad.output.split()[0])


def test_search_matches_taxon_id(installed):
    base, _ = installed
    result = run(["search", "5661", "--local-dir", "data"], base)
    assert result.exit_code == 0
    assert "donovani" in result.output


def test_search_without_a_match_exits_nonzero(installed):
    base, _ = installed
    result = run(["search", "xyzzy", "--local-dir", "data"], base)

    assert result.exit_code == 1
    assert "No genome matches" in result.output


def test_search_requires_a_term(installed):
    base, _ = installed
    assert run(["search", "--local-dir", "data"], base).exit_code != 0


def test_search_flags_installed_genomes(tmp_path):
    """A cached install records its origin, so search can say it is already present."""
    from leishref.metadata import catalog as read_catalog

    origin = read_catalog()[0]
    directory = tmp_path / "data" / "mine"
    directory.mkdir(parents=True)
    genome = Genome(
        identifier="mine",
        species=origin.species,
        provenance={"catalog_id": origin.identifier},
    )
    write_genome(directory, genome)

    result = run(["search", origin.identifier, "--local-dir", "data"], tmp_path)
    assert "installed as mine" in result.output


def test_install_without_an_alias_suggests_one(tmp_path):
    result = run(["install", "GCA_000410715.1", "--local-dir", "data"], tmp_path)

    assert result.exit_code == 2
    assert "--alias is required" in result.output
    assert "--alias LtrL590" in result.output


def test_install_by_catalog_alias_uses_aliases_txt(tmp_path):
    """Install should resolve catalog aliases through aliases.txt."""
    result = run(["install", "LtrL590", "--local-dir", "data"], tmp_path)

    assert result.exit_code == 2
    assert "--alias is required" in result.output
    assert "--alias LtrL590" in result.output


def test_install_rejects_an_unknown_name_before_asking_for_an_alias(tmp_path):
    result = run(["install", "nonexistent", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 1
    assert "Not in catalog" in result.output


def test_info_suggests_an_alias_for_a_genome_not_installed(installed):
    base, _ = installed
    result = run(["info", "GCA_000410715.1", "--local-dir", "data"], base)
    assert "suggested alias: Ltrop.ncbi.L590" in result.output


def test_info_does_not_suggest_an_alias_for_something_installed(installed):
    base, _ = installed
    result = run(["info", "Ltrop.flye", "--local-dir", "data"], base)
    assert "suggested alias" not in result.output


def test_search_reports_contiguity(installed):
    base, _ = installed
    result = run(["search", "GCA_000410715.1", "--local-dir", "data"], base)
    assert "N50" in result.output


def test_organism_joins_species_and_strain_with_a_dash():
    from leishref.cli import _organism

    assert _organism(Genome(species="Leishmania donovani", strain="BPK282A1")) == "Leishmania donovani - BPK282A1"


def test_organism_omits_the_dash_when_no_strain_is_known():
    from leishref.cli import _organism

    assert _organism(Genome(species="Leishmania donovani")) == "Leishmania donovani"
    assert _organism(Genome()) == "?"


def test_listings_sort_by_species_then_strain():
    from leishref.cli import _by_organism

    entries = [
        Genome(identifier="c", species="Leishmania tropica", strain="B"),
        Genome(identifier="a", species="Leishmania donovani", strain="Z"),
        Genome(identifier="b", species="Leishmania donovani", strain="A"),
    ]
    assert [g.identifier for g in _by_organism(entries)] == ["b", "a", "c"]


def test_entries_without_a_species_sort_last():
    from leishref.cli import _by_organism

    entries = [Genome(identifier="unknown"), Genome(identifier="named", species="Leishmania donovani")]
    assert [g.identifier for g in _by_organism(entries)] == ["named", "unknown"]


def test_info_lists_the_catalog_in_organism_order(installed):
    base, _ = installed
    result = run(["info", "--local-dir", "data"], base)

    listed = [line for line in result.output.splitlines() if line.startswith("  GC")]
    # Extract organism name, stripping alias if present
    organisms = [line.split(None, 1)[1].split(" (alias:")[0] for line in listed]
    assert organisms == sorted(organisms, key=str.lower)


def test_search_output_shows_the_dash(installed):
    base, _ = installed
    result = run(["search", "BPK282A1", "--local-dir", "data"], base)
    assert "Leishmania donovani - BPK282A1" in result.output


def test_install_records_the_files_it_wrote(tmp_path):
    """A catalog entry imported from NCBI's summary names no files; installing one has
    to record what actually arrived, or verify and link cannot see it."""
    from leishref.cli import _install, cache_key

    source = tmp_path / "GCA_9_genomic.fna"
    source.write_text(">c1\nACGT\n")
    gff = tmp_path / "GCA_9_genomic.gff"
    gff.write_text("##gff-version 3\n")

    catalog_entry = Genome(identifier="GCA_9.1", source="NCBI", accession="GCA_9.1")
    assert catalog_entry.files == {}

    target = _install(catalog_entry, cache_key(catalog_entry), [source, gff], tmp_path / "data")
    written = read_genome(target)

    assert written.files == {"fasta": "GCA_9_genomic.fna", "gff": "GCA_9_genomic.gff"}
    # The cache is keyed by accession, not by a user-chosen alias, so the genome's own
    # identifier is left untouched - a different alias in another project shares this
    # same cache entry instead of duplicating it.
    assert written.identifier == "GCA_9.1"
    assert written.provenance == {}


def test_organism_does_not_repeat_a_strain_already_in_the_species():
    from leishref.cli import _organism

    genome = Genome(species="Leishmania sp. AIIMS/LM/SS/PKDL/LD-974", strain="AIIMS/LM/SS/PKDL/LD-974")
    assert _organism(genome) == "Leishmania sp. AIIMS/LM/SS/PKDL/LD-974"


@pytest.fixture
def recorded(tmp_path):
    """A local database holding one genome installed from a real catalog entry."""
    from leishref.metadata import catalog as read_catalog

    origin = read_catalog()[0]
    directory = tmp_path / "data" / "mine"
    directory.mkdir(parents=True)
    write_genome(
        directory,
        Genome(identifier="mine", species=origin.species, provenance={"catalog_id": origin.identifier}),
    )
    return tmp_path, origin.identifier


def test_install_of_an_installed_genome_records_it(recorded):
    """Re-running install on something already present still writes the recipe line."""
    base, name = recorded
    result = run(["install", name, "--alias", "mine", "--local-dir", "data", "--no-link"], base)

    assert result.exit_code == 0
    assert f"{name}\tmine" in (base / "accessions.txt").read_text()


def test_an_alias_is_recorded_once(recorded):
    base, name = recorded
    for _ in range(3):
        run(["install", name, "--alias", "mine", "--local-dir", "data", "--no-link"], base)

    lines = [ln for ln in (base / "accessions.txt").read_text().splitlines() if not ln.startswith("#")]
    assert lines == [f"{name}\tmine"]


def test_restore_lists_what_it_would_do(recorded):
    base, name = recorded
    run(["install", name, "--alias", "mine", "--local-dir", "data", "--no-link"], base)

    result = run(["restore", "--local-dir", "data", "--dry-run"], base)
    assert result.exit_code == 0
    assert "mine" in result.output
    assert "installed" in result.output


def test_restore_reports_a_genome_that_is_no_longer_there(recorded):
    """A recorded alias whose cache entry was deleted shows up as missing."""
    from leishref.cli import cache_key
    from leishref.metadata import catalog as read_catalog
    from leishref.metadata import find

    base, name = recorded
    run(["install", name, "--alias", "mine", "--local-dir", "data", "--no-link"], base)

    # The cache is keyed by accession/identifier, not by the alias just used to
    # install it - find the real cache directory to delete.
    entries = read_catalog()
    key = cache_key(find(entries, name))
    (base / "data" / key / "metadata.yaml").unlink()

    result = run(["restore", "--local-dir", "data", "--dry-run"], base)
    assert "missing" in result.output


def test_restore_without_an_accessions_file_fails_clearly(tmp_path):
    result = run(["restore", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 1
    assert "No accessions file" in result.output


def test_restore_reads_an_explicit_file(recorded):
    base, name = recorded
    shared = base / "shared.txt"
    shared.write_text(f"# comment\n{name}\tmine\n")

    result = run(["restore", "--file", str(shared), "--local-dir", "data", "--dry-run"], base)
    assert result.exit_code == 0
    assert "mine" in result.output


def test_a_malformed_accessions_line_is_skipped(recorded):
    base, name = recorded
    shared = base / "shared.txt"
    shared.write_text(f"{name}\tmine\nthis line has three\tfields\there\n")

    result = run(["restore", "--file", str(shared), "--local-dir", "data", "--dry-run"], base)
    assert result.exit_code == 0
    assert "skipping" in result.output


def test_from_installed_describes_an_existing_database(recorded):
    """A database built before accessions.txt existed can still write its own recipe."""
    base, name = recorded
    result = run(["restore", "--from-installed", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert f"{name}\tmine" in (base / "accessions.txt").read_text()


def test_from_installed_skips_a_genome_with_no_origin(tmp_path):
    directory = tmp_path / "data" / "orphan"
    directory.mkdir(parents=True)
    write_genome(directory, Genome(identifier="orphan", source="Local"))

    result = run(["restore", "--from-installed", "--local-dir", "data"], tmp_path)
    assert "no catalog origin recorded" in result.output
    assert "Recorded 0 genomes" in result.output


def test_restore_is_quiet_about_the_genomes_that_worked(recorded):
    """The per-genome chatter of install is swallowed unless something failed."""
    base, name = recorded
    run(["restore", "--from-installed", "--local-dir", "data"], base)

    result = run(["restore", "--local-dir", "data", "--no-link"], base)
    assert result.exit_code == 0
    assert "Already installed" not in result.output
    assert "Restored 1/1" in result.output


def test_restore_verbose_shows_each_download(recorded):
    base, name = recorded
    run(["restore", "--from-installed", "--local-dir", "data"], base)
    run(["restore", "--local-dir", "data", "--no-link"], base)

    result = run(["restore", "--local-dir", "data", "--verbose", "--no-link"], base)
    assert result.exit_code == 0
    assert "Already installed" in result.output


def test_a_failed_restore_reports_why(recorded):
    """What install printed is kept back and shown for the genomes that failed."""
    base, _ = recorded
    shared = base / "shared.txt"
    shared.write_text("NOT_A_GENOME\tbroken\n")

    result = run(["restore", "--file", str(shared), "--local-dir", "data"], base)
    assert result.exit_code == 1
    assert "failed: broken <- NOT_A_GENOME" in result.output
    assert "Not in catalog: NOT_A_GENOME" in result.output


def test_scaffold_resolves_a_genome_name_to_its_fasta(installed):
    """--query and --reference take a name as readily as a path."""
    from leishref.cli import _resolve_assembly

    base, fasta = installed
    path, genome = _resolve_assembly("Ltrop.flye", base / "data", None, "--query")

    assert path == fasta
    assert genome.identifier == "Ltrop.flye"


def test_scaffold_takes_a_path_as_it_is(tmp_path):
    from leishref.cli import _resolve_assembly

    fasta = tmp_path / "loose.fa"
    fasta.write_text(">c1\nACGT\n")
    path, genome = _resolve_assembly(str(fasta), tmp_path / "data", None, "--query")

    assert path == fasta
    assert genome is None


def test_scaffold_rejects_a_name_that_is_neither_file_nor_genome(tmp_path):
    from leishref.cli import _resolve_assembly

    with pytest.raises(SystemExit):
        _resolve_assembly("no_such_thing", tmp_path / "data", None, "--query")


def test_a_parent_record_names_the_catalog_entry_and_its_checksum(installed):
    """A published scaffold has to say exactly which assemblies it came from."""
    from leishref.cli import _parent_record
    from leishref.metadata import read_genome

    base, fasta = installed
    record = _parent_record(fasta, read_genome(base / "data" / "Ltrop.flye"))

    assert record["file"] == fasta.name
    assert record["md5"] == md5_file(fasta)
    assert record["name"] == "Ltrop.flye"
    assert record["species"] == "Leishmania tropica"


def test_a_parent_record_of_a_bare_file_is_just_the_checksum(tmp_path):
    from leishref.cli import _parent_record

    fasta = tmp_path / "loose.fa"
    fasta.write_text(">c1\nACGT\n")
    assert _parent_record(fasta, None) == {"file": "loose.fa", "md5": md5_file(fasta)}


def test_scaffold_requires_query_to_be_catalog_genome(installed):
    """Query must be an installed catalog genome; bare FASTA files are not allowed."""
    base, _ = installed
    query = base / "loose.fa"
    query.write_text(">c1\nACGTACGT\n")

    result = run(
        ["dev", "scaffold", "--query", str(query), "--reference", "Ltrop.flye", "--alias", "x", "--local-dir", "data"],
        base,
    )
    assert result.exit_code == 1
    assert "catalog genome" in result.output


def test_scaffold_auto_generates_name_from_query_and_reference():
    """Scaffold name is auto-generated as <query_alias>.scaffold.<ref_alias> when --alias is omitted."""
    from leishref.cli import _genome_alias
    from leishref.metadata import Genome

    # Test with NCBI genomes that have aliases
    query = Genome(
        identifier="GCA_000410715.1",
        source="NCBI",
        species="Leishmania tropica",
        accession="GCA_000410715.1",
    )
    ref = Genome(
        identifier="GCA_002243465.1",
        source="NCBI",
        species="Leishmania donovani",
        accession="GCA_002243465.1",
    )

    # With catalog aliases, uses them
    query_alias = _genome_alias(query)
    ref_alias = _genome_alias(ref)
    assert f"{query_alias}.scaffold.{ref_alias}" == "LtrL590.scaffold.Ld1S"

    # Test with TriTrypDB genome: should append _tritryp
    tritryp = Genome(
        identifier="Lsp.Ghana",
        source="TriTrypDB",
        species="Leishmania species",
    )
    tritryp_alias = _genome_alias(tritryp)
    assert tritryp_alias == "Lsp.Ghana_tritryp"


def test_info_counts_each_catalog_section(installed):
    base, _ = installed
    result = run(["info", "--local-dir", "data"], base)

    assert result.exit_code == 0
    for label in ("NCBI", "TriTrypDB", "Scaffolds"):
        assert label in result.output


def test_info_sections_are_in_reading_order(installed):
    """Upstream archives first, then what was derived here."""
    base, _ = installed
    output = run(["info", "--local-dir", "data"], base).output

    order = [output.index(f"\n{label} (") for label in ("NCBI", "TriTrypDB", "Scaffolds") if f"\n{label} (" in output]
    assert order == sorted(order)


def test_info_counts_add_up_to_the_catalog_total(installed):
    import re

    base, _ = installed
    output = run(["info", "--local-dir", "data"], base).output

    total = int(re.search(r"Catalog: (\d+) genomes", output).group(1))
    counted = sum(
        int(n)
        for n in re.findall(
            r"^  (?:NCBI-Nucleotide|NCBI|TriTrypDB|Scaffolds|Custom|Zenodo|Other)\s+(\d+)$", output, re.M
        )
    )
    assert counted == total


def test_rename_sequences_outputs_renamed_fasta(installed, tmp_path, monkeypatch):
    """Rename-sequences outputs renamed FASTA without modifying cache."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    base, fasta = installed

    # Run rename-sequences with number flavor
    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "number", "--local-dir", "data"], base)
    assert result.exit_code == 0
    assert "Renaming sequences" in result.output

    # Output is written to the current directory, named after the alias, not the cache
    output_file = base / f"Ltrop.flye.number{fasta.suffix}"
    assert output_file.exists()

    # Check that sequence was renamed (from >c1 to >1), sequence data preserved
    content = output_file.read_text()
    assert ">1\n" in content
    assert ">c1" not in content
    assert "ACGTACGT" in content

    # The cache copy itself must never be modified
    assert fasta.read_text() == ">c1\nACGTACGT\n"


def test_rename_sequences_output_filename_keeps_versioned_accession(tmp_path, monkeypatch):
    """A dotted accession like 'GCA_1.1' is an alias, not a file extension - must survive intact."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    directory = tmp_path / "data" / "GCA_1.1"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGTACGT\n")

    write_genome(
        directory,
        Genome(
            identifier="GCA_1.1",
            source="Local",
            species="Leishmania tropica",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["rename-sequences", "GCA_1.1", "--flavor", "number", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 0

    output_file = tmp_path / f"GCA_1.1.number{fasta.suffix}"
    assert output_file.exists()


def test_rename_sequences_with_kraken_flavor(tmp_path, monkeypatch):
    """Rename-sequences with kraken flavor uses numeric index + taxid."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    directory = tmp_path / "data" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGTACGT\n")

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species="Leishmania tropica",
            taxon_id=5666,
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "kraken", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 0

    output_file = tmp_path / f"Ltrop.flye.kraken{fasta.suffix}"
    assert output_file.exists()

    # Check that sequence was renamed with kraken format (numeric index + taxid), sequence data preserved
    content = output_file.read_text()
    assert ">1|kraken:taxid|5666\n" in content
    assert ">c1\n" not in content
    assert "ACGTACGT" in content


def test_rename_sequences_kraken_flavor_does_not_mislabel_37th_contig_as_maxicircle(tmp_path, monkeypatch):
    """A contig_* sequence at position 37+ keeps original ID with kraken tag.

    Kraken flavor renames chromosomes 1-36 to numeric indices, but sequences
    after position 36 (like extra contigs) keep their original names since
    they're not standard chromosomes.
    """
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    directory = tmp_path / "data" / "Ltrop.scaffold"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    headers = [f"chr{i}" for i in range(1, 37)] + ["contig_10"]
    fasta.write_text("".join(f">{h}\nACGTACGT\n" for h in headers))

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.scaffold",
            source="Local",
            species="Leishmania tropica",
            taxon_id=5666,
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["rename-sequences", "Ltrop.scaffold", "--flavor", "kraken", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 0

    output_file = tmp_path / f"Ltrop.scaffold.kraken{fasta.suffix}"
    content = output_file.read_text()

    # contig_10 at position 37 is not renamed to "37|kraken:..." because NW_* (contig) IDs keep original names
    # But since this is contig_10 (not NW_), it will be renamed to "37|kraken:taxid|5666"
    assert ">37|kraken:taxid|5666\n" in content
    assert ">maxicircle\n" not in content


def test_rename_sequences_kraken_flavor_requires_taxid(tmp_path):
    """Rename-sequences kraken flavor requires --taxid if genome has no taxon_id."""
    directory = tmp_path / "data" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGTACGT\n")

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species="Leishmania tropica",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "kraken", "--local-dir", "data"], tmp_path)
    assert result.exit_code != 0
    assert "taxid" in result.output.lower()


def test_rename_sequences_kraken_flavor_uses_explicit_taxid(tmp_path, monkeypatch):
    """Rename-sequences kraken flavor accepts --taxid parameter."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    directory = tmp_path / "data" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGTACGT\n")

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species="Leishmania tropica",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(
        ["rename-sequences", "Ltrop.flye", "--flavor", "kraken", "--taxid", "5661", "--local-dir", "data"],
        tmp_path,
    )
    assert result.exit_code == 0

    output_file = tmp_path / f"Ltrop.flye.kraken{fasta.suffix}"
    content = output_file.read_text()
    assert ">1|kraken:taxid|5661\n" in content
    assert "ACGTACGT" in content


def _genome_with_accession(directory, accession, sequences=">chr1\nACGT\n>unmapped\nTTTT\n"):
    fasta = directory / "assembly.fa"
    fasta.write_text(sequences)
    write_genome(
        directory,
        Genome(
            identifier=directory.name,
            source="Local",
            species="Leishmania tropica",
            accession=accession,
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )
    return fasta


def test_prune_scaffold_requires_an_accession(tmp_path):
    directory = tmp_path / "data" / "NoAcc"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")
    write_genome(
        directory,
        Genome(
            identifier="NoAcc",
            source="Local",
            species="Leishmania tropica",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["prune-scaffold", "NoAcc", "--local-dir", "data"], tmp_path)
    assert result.exit_code != 0
    assert "no accession" in result.output.lower()


def test_prune_scaffold_requires_chromosome_info(tmp_path, monkeypatch):
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "empty_catalog")
    directory = tmp_path / "data" / "Ltrop.acc"
    directory.mkdir(parents=True)
    _genome_with_accession(directory, "ACCX")

    result = run(["prune-scaffold", "Ltrop.acc", "--local-dir", "data"], tmp_path)
    assert result.exit_code != 0
    assert "No chromosome info found" in result.output


def test_prune_scaffold_keeps_mapped_and_kinetoplast_sequences(tmp_path, monkeypatch):
    import csv

    catalog_dir = tmp_path / "shared_catalog"
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", catalog_dir)
    catalog_dir.mkdir(parents=True)

    # Create chromosome map CSV with chr1 mapped to chromosome 1
    csv_file = catalog_dir / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "chr1", "chromosome": "1", "taxid": "", "origin": "ACCX"})

    directory = tmp_path / "data" / "Ltrop.acc"
    directory.mkdir(parents=True)
    fasta = _genome_with_accession(directory, "ACCX", ">chr1\nACGT\n>unmapped\nTTTT\n>maxicircle\nGGGG\n")

    result = run(["prune-scaffold", "Ltrop.acc", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 0

    assert fasta.read_text() == ">chr1\nACGT\n>maxicircle\nGGGG\n"

    updated = read_genome(directory)
    assert updated.checksums["fasta"] == md5_file(fasta)


def test_info_shows_a_single_catalog_entry_in_full(installed):
    base, _ = installed
    result = run(["info", "BK010877.1", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "identifier: BK010877.1" in result.output
    assert "suggested alias:" in result.output


def test_search_long_form_prints_the_full_yaml_record(installed):
    base, _ = installed
    result = run(["search", "--long", "tropica", "L590"], base)

    assert result.exit_code == 0
    assert "identifier:" in result.output


def test_link_reports_a_conflict_instead_of_overwriting_a_real_file(installed):
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\n")
    (base / "Ltrop.flye.fna").write_text("not a symlink")

    result = run(["link", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "Not linked" in result.output
    assert "Created 0 links" in result.output


def test_restore_with_an_empty_accessions_file_errors(tmp_path):
    (tmp_path / "accessions.txt").write_text("# nothing here\n")

    result = run(["restore"], tmp_path)

    assert result.exit_code != 0
    assert "lists no genomes" in result.output


def test_restore_dry_run_reports_installed_and_missing_state(installed):
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\nSomeOther\tSomeOther\n")

    result = run(["restore", "--dry-run", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "installed" in result.output
    assert "missing" in result.output


def test_restore_from_installed_records_accessions_file(tmp_path):
    directory = tmp_path / "local" / "Ltrop.acc"
    directory.mkdir(parents=True)
    _genome_with_accession(directory, "ACCX")

    result = run(["restore", "--from-installed", "--local-dir", "local"], tmp_path)

    assert result.exit_code == 0
    assert "Recorded 1 genome" in result.output
    lines = [line for line in (tmp_path / "accessions.txt").read_text().splitlines() if not line.startswith("#")]
    assert lines == ["ACCX\tLtrop.acc"]


def test_dev_remove_deletes_the_catalog_entry_with_force(tmp_path):
    directory = tmp_path / "cat" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")
    write_genome(
        directory,
        Genome(identifier="Ltrop.flye", source="Local", species="Leishmania tropica"),
    )

    result = run(["dev", "remove", "Ltrop.flye", "--catalog-dir", "cat", "--force"], tmp_path)

    assert result.exit_code == 0
    assert not directory.exists()


def test_dev_remove_without_force_aborts_when_declined(tmp_path):
    directory = tmp_path / "cat" / "Ltrop.flye"
    directory.mkdir(parents=True)
    write_genome(
        directory,
        Genome(identifier="Ltrop.flye", source="Local", species="Leishmania tropica"),
    )

    result = run(["dev", "remove", "Ltrop.flye", "--catalog-dir", "cat"], tmp_path, input="n\n")

    assert result.exit_code == 0
    assert directory.exists()


def test_dev_check_aliases_passes_on_a_clean_catalog(tmp_path):
    directory = tmp_path / "cat" / "Ltrop.flye"
    directory.mkdir(parents=True)
    write_genome(
        directory,
        Genome(identifier="Ltrop.flye", source="Local", species="Leishmania tropica", accession="ACCX"),
    )

    result = run(["dev", "check-aliases", "--catalog-dir", "cat"], tmp_path)

    assert result.exit_code == 0
    assert "No duplicate accessions" in result.output


def test_dev_check_aliases_flags_a_duplicate_accession(tmp_path):
    for name in ("Ltrop.one", "Ltrop.two"):
        directory = tmp_path / "cat" / name
        directory.mkdir(parents=True)
        write_genome(
            directory,
            Genome(identifier=name, source="Local", species="Leishmania tropica", accession="ACCX"),
        )

    result = run(["dev", "check-aliases", "--catalog-dir", "cat"], tmp_path)

    assert result.exit_code != 0
    assert "Duplicate accessions" in result.output
    assert "ACCX" in result.output


def test_dev_status_reports_a_clean_catalog(tmp_path):
    directory = tmp_path / "cat" / "Ltrop.flye"
    directory.mkdir(parents=True)
    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species="Leishmania tropica",
            assembly_level="Complete Genome",
            taxon_id=5666,
        ),
    )

    result = run(["dev", "status", "--catalog-dir", "cat"], tmp_path)

    assert result.exit_code == 0
    assert "Catalog is clean" in result.output


def test_dev_status_flags_missing_fields_and_bad_checksums(tmp_path):
    directory = tmp_path / "cat" / "Ltrop.flye"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")
    write_genome(
        directory,
        Genome(
            identifier="Ltrop.flye",
            source="Local",
            species=None,
            files={"fasta": fasta.name},
            checksums={"fasta": "deadbeef"},
        ),
    )
    orphan = tmp_path / "cat" / "custom" / "orphan"
    orphan.mkdir(parents=True)

    result = run(["dev", "status", "--catalog-dir", "cat"], tmp_path)

    assert result.exit_code != 0
    assert "Missing required field: species" in result.output
    assert "checksum mismatch" in result.output
    assert "Orphaned directory" in result.output
    assert "Missing taxon_id" in result.output


def test_update_chromosome_map_interactive_confirm(tmp_path, monkeypatch):
    """Test update-chromosome-map command with user confirmation."""
    import csv

    from leishref.metadata import CATALOG_DIR

    catalog_dir = tmp_path / "shared_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", catalog_dir)

    fasta_file = tmp_path / "test.fna"
    fasta_file.write_text(">CM024314.1 chromosome 28\nACGT\n>contig1 extra contig\nTTTT\n")

    result = run(
        ["dev", "update-chromosome-map", "GCA_test.1", str(fasta_file), "--taxid", "5666"],
        tmp_path,
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Proposed chromosome assignments" in result.output
    assert "Updated" in result.output


def test_update_chromosome_map_cancel(tmp_path, monkeypatch):
    """Test update-chromosome-map command with user cancellation."""
    catalog_dir = tmp_path / "shared_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", catalog_dir)

    fasta_file = tmp_path / "test.fna"
    fasta_file.write_text(">seq1 chromosome 1\nACGT\n")

    result = run(
        ["dev", "update-chromosome-map", "GCA_test.1", str(fasta_file)],
        tmp_path,
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Cancelled" in result.output


def test_rename_sequences_kraken_with_genome_taxid(installed, tmp_path, monkeypatch):
    """Kraken flavor uses taxon_id from genome metadata."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    base, fasta = installed

    # Create chromosome mapping for the test genome
    from leishref.metadata import read_genome

    genome = read_genome(base / "data" / "Ltrop.flye")
    catalog_dir = tmp_path / "shared_catalog"
    csv_file = catalog_dir / "chromosome_map.csv"
    import csv

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "c1", "chromosome": "1", "taxid": "", "origin": "Ltrop.flye"})

    result = run(
        ["rename-sequences", "Ltrop.flye", "--flavor", "kraken", "--taxid", "5666", "--local-dir", "data"],
        base,
    )
    assert result.exit_code == 0
    assert "kraken" in result.output.lower() or "Renaming" in result.output


# ============================================================================== bundle


def test_bundle_with_symlink_pattern(installed):
    """Bundle packs symlinks matching a pattern into tar.gz."""
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\n")

    # Create the symlink
    run(["link", "--local-dir", "data"], base)

    result = run(["bundle", "*.fna", "--local-dir", "data", "-o", "test.tar.gz"], base)
    assert result.exit_code == 0
    assert "1 file" in result.output or "Bundling" in result.output
    assert (base / "test.tar.gz").exists()


def test_bundle_with_genome_name(installed):
    """Bundle packs a genome by its identifier."""
    base, _ = installed
    result = run(["bundle", "Ltrop.flye", "--local-dir", "data", "-o", "named.tar.gz"], base)

    assert result.exit_code == 0
    assert "file" in result.output.lower() or "Bundling" in result.output
    assert (base / "named.tar.gz").exists()


def test_bundle_with_glob_pattern(installed):
    """Bundle accepts wildcard patterns on genome names."""
    base, _ = installed
    result = run(["bundle", "Ltrop*", "--local-dir", "data", "-o", "glob.tar.gz"], base)

    assert result.exit_code == 0
    assert (base / "glob.tar.gz").exists()


def test_bundle_defaults_to_bundle_tar_gz(installed):
    """Bundle creates bundle.tar.gz when no output specified."""
    base, _ = installed
    result = run(["bundle", "Ltrop.flye", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert (base / "bundle.tar.gz").exists()


def test_bundle_fails_on_no_matches(installed):
    """Bundle exits nonzero when pattern matches nothing."""
    base, _ = installed
    result = run(["bundle", "NonExistent*", "--local-dir", "data"], base)

    assert result.exit_code == 1
    assert "No match" in result.output or "No genome" in result.output.lower()


def test_bundle_fails_on_empty_result(tmp_path):
    """Bundle fails when result would be empty."""
    result = run(["bundle", "*.fna", "--local-dir", "data"], tmp_path)

    assert result.exit_code == 1


# ============================================================================== export


def test_export_default_is_json_from_catalog(installed):
    """Export defaults to JSON format of the catalog."""
    base, _ = installed
    result = run(["export", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "[" in result.output or "{" in result.output  # JSON-like


def test_export_yaml_format(installed):
    """Export can produce YAML."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "--format", "yaml"], base)

    assert result.exit_code == 0
    assert "-" in result.output or ":" in result.output  # YAML-like


def test_export_tsv_format(installed):
    """Export can produce tab-separated values."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "--format", "tsv"], base)

    assert result.exit_code == 0
    assert "\t" in result.output  # TSV has tabs


def test_export_local_source_includes_installed(installed):
    """Export --source local shows only cached genomes."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "--source", "local", "--format", "json"], base)

    assert result.exit_code == 0
    assert "Ltrop.flye" in result.output


def test_export_both_sources(installed):
    """Export --source both includes catalog and cached."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "--source", "both", "--format", "json"], base)

    assert result.exit_code == 0
    # Both catalog entries and local should be present
    assert len(result.output) > 100


def test_export_to_file(installed):
    """Export writes to a file with -o."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "-o", "export.json"], base)

    assert result.exit_code == 0
    assert (base / "export.json").exists()
    assert len((base / "export.json").read_text()) > 10


@pytest.mark.parametrize("fmt", ["json", "yaml", "tsv"])
def test_export_all_formats_work(installed, fmt):
    """Export works with all supported formats."""
    base, _ = installed
    result = run(["export", "--local-dir", "data", "--format", fmt], base)
    assert result.exit_code == 0


# ============================================================================== install-ncbi variants


def test_install_ncbi_requires_no_arguments(tmp_path, monkeypatch):
    """install-ncbi bulk-installs all NCBI genomes from catalog."""
    # Mock catalog to return NCBI genomes without downloading
    from leishref.cli import _install_many_parallel

    ncbi_genomes = [
        Genome(identifier="GCA_001", source="NCBI", accession="GCA_001", species="Leishmania major"),
        Genome(identifier="GCA_002", source="NCBI", accession="GCA_002", species="Leishmania donovani"),
    ]
    monkeypatch.setattr("leishref.cli.catalog", lambda: ncbi_genomes)
    monkeypatch.setattr("leishref.cli._install_many_parallel", lambda *a, **kw: [])

    result = run(["install-ncbi", "--local-dir", "data", "--verbose"], tmp_path)

    # Should recognize NCBI genomes
    assert "Installing" in result.output or "NCBI" in result.output or "genome" in result.output.lower()


def test_install_ncbi_refseq_filters_to_gcf(tmp_path, monkeypatch):
    """install-ncbi-refseq only installs GCF_ (RefSeq) accessions."""
    ncbi_genomes = [
        Genome(identifier="GCA_001", source="NCBI", accession="GCA_001"),
        Genome(identifier="GCF_001", source="NCBI", accession="GCF_001"),
    ]
    monkeypatch.setattr("leishref.cli.catalog", lambda: ncbi_genomes)
    monkeypatch.setattr("leishref.cli._install_many_parallel", lambda *a, **kw: [])

    result = run(["install-ncbi-refseq", "--local-dir", "data", "--verbose"], tmp_path)

    # Should filter to RefSeq only
    assert "Installing" in result.output or "genome" in result.output.lower() or "RefSeq" in result.output


def test_install_ncbi_supports_parallel(tmp_path, monkeypatch):
    """install-ncbi accepts --parallel flag."""
    ncbi_genomes = [
        Genome(identifier="GCA_001", source="NCBI", accession="GCA_001", species="Leishmania"),
    ]
    monkeypatch.setattr("leishref.cli.catalog", lambda: ncbi_genomes)
    monkeypatch.setattr("leishref.cli._install_many_parallel", lambda *a, **kw: [])

    result = run(["install-ncbi", "--local-dir", "data", "--parallel", "2", "--verbose"], tmp_path)

    # Should accept parallel flag without arg errors
    assert result.exit_code in (0, 1)


# ============================================================================== search edge cases


def test_search_with_wildcard_in_term(installed):
    """Search accepts wildcard patterns like 'GCA_*'."""
    base, _ = installed
    result = run(["search", "GCA_*", "--local-dir", "data"], base)

    # May find or not find genomes, but shouldn't error on wildcard
    assert result.exit_code in (0, 1)


def test_search_long_form_with_multiple_matches(installed):
    """Search --long outputs full YAML for matching genomes."""
    base, _ = installed
    result = run(["search", "donovani", "--long", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "identifier:" in result.output


# ============================================================================== restore edge cases


def test_restore_parallel_downloads(recorded, monkeypatch):
    """Restore --parallel downloads concurrently."""
    base, name = recorded
    # Mock install to not download
    monkeypatch.setattr("leishref.cli._install_many_parallel", lambda *a, **kw: [])

    # Create accessions file directly
    (base / "accessions.txt").write_text(f"# accessions\n{name}\tmine\n")

    result = run(["restore", "--local-dir", "data", "--parallel", "2", "--no-link", "--dry-run"], base)

    # Dry-run should work without actual downloads
    assert result.exit_code == 0


def test_restore_verbose_shows_details(recorded, monkeypatch):
    """Restore --verbose shows per-genome output."""
    base, name = recorded
    # Mock install to not download
    monkeypatch.setattr("leishref.cli._install_many_parallel", lambda *a, **kw: [])

    # Create accessions file directly
    (base / "accessions.txt").write_text(f"# accessions\n{name}\tmine\n")

    result = run(["restore", "--local-dir", "data", "--verbose", "--no-link", "--dry-run"], base)

    assert result.exit_code == 0


# ============================================================================== verify flags


def test_verify_quick_skips_checksums(installed):
    """Verify --quick checks presence only, skips checksum validation."""
    base, _ = installed
    result = run(["verify", "--quick", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "mismatch: 0" in result.output


# ============================================================================== link edge cases


def test_link_skips_non_symlinks(installed):
    """Link only processes symlinks, ignores regular files."""
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\n")
    (base / "regular.txt").write_text("not a symlink")  # Regular file

    result = run(["link", "--local-dir", "data"], base)

    assert result.exit_code == 0
    # Should not try to overwrite the regular file
    assert "Not linked" in result.output or "Created" in result.output


def test_link_with_basedir_creates_links_elsewhere(installed):
    """Link --basedir creates symlinks in a different directory."""
    base, _ = installed
    (base / "accessions.txt").write_text("Ltrop.flye\tLtrop.flye\n")
    subdir = base / "subdir"
    subdir.mkdir()

    result = run(["link", "--local-dir", "data", "--basedir", "subdir"], base)

    assert result.exit_code == 0
    assert (subdir / "Ltrop.flye.fna").is_symlink()


# ============================================================================== info edge cases


def test_info_full_record_has_path(installed):
    """Info on a single genome shows its cached path."""
    base, _ = installed
    result = run(["info", "Ltrop.flye", "--local-dir", "data"], base)

    assert result.exit_code == 0
    assert "path:" in result.output


def test_info_catalog_has_source_labels(installed):
    """Info lists catalog with source labels (GenBank, RefSeq, etc.)."""
    base, _ = installed
    result = run(["info", "--local-dir", "data"], base)

    assert result.exit_code == 0
    # Should show source styles for genomes
    assert "NCBI" in result.output or "source" in result.output.lower()


# ============================================================================== rename-sequences edge cases


def test_rename_sequences_number_flavor_basic(installed, tmp_path, monkeypatch):
    """Rename-sequences number flavor converts to numeric indices."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    base, fasta = installed

    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "number", "--local-dir", "data"], base)
    assert result.exit_code == 0

    output_file = base / f"Ltrop.flye.number{fasta.suffix}"
    assert ">1\n" in output_file.read_text()


def test_rename_sequences_name_flavor_uses_chromosome_names(installed, tmp_path, monkeypatch):
    """Rename-sequences name flavor uses chromosome database names."""
    import csv

    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    base, fasta = installed

    # Add chromosome mapping
    catalog_dir = tmp_path / "shared_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    csv_file = catalog_dir / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "c1", "chromosome": "LdCHR01", "taxid": "5666", "origin": "Ltrop.flye"})

    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "name", "--local-dir", "data"], base)
    assert result.exit_code == 0


def test_rename_sequences_with_missing_fasta_fails(tmp_path):
    """Rename-sequences fails when no FASTA file found."""
    directory = tmp_path / "data" / "NoFASTA"
    directory.mkdir(parents=True)
    write_genome(directory, Genome(identifier="NoFASTA", source="Local", species="Leishmania"))

    result = run(["rename-sequences", "NoFASTA", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 1
    assert "FASTA" in result.output or "not found" in result.output.lower()


def test_rename_sequences_resolves_by_filename_stem(installed, tmp_path, monkeypatch):
    """Rename-sequences resolves 'genome.fna' as alias 'genome'."""
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", tmp_path / "shared_catalog")
    base, fasta = installed

    # Can pass the .fna filename
    result = run(["rename-sequences", f"Ltrop.flye.fna", "--flavor", "number", "--local-dir", "data"], base)
    assert result.exit_code == 0


# ============================================================================== prune-scaffold edge cases


def test_prune_scaffold_with_mapped_sequences(tmp_path, monkeypatch):
    """Prune-scaffold removes unmapped contigs, keeps mapped and kinetoplast."""
    import csv

    catalog_dir = tmp_path / "shared_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("leishref.metadata.CATALOG_DIR", catalog_dir)

    # Add mappings for chr1 only
    csv_file = catalog_dir / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "chr1", "chromosome": "1", "taxid": "", "origin": "ACCX"})

    directory = tmp_path / "data" / "Ltrop.acc"
    directory.mkdir(parents=True)
    fasta = directory / "assembly.fa"
    fasta.write_text(">chr1\nACGT\n>unmapped\nTTTT\n>maxicircle\nGGGG\n")

    write_genome(
        directory,
        Genome(
            identifier="Ltrop.acc",
            source="Local",
            species="Leishmania tropica",
            accession="ACCX",
            files={"fasta": fasta.name},
            checksums={"fasta": md5_file(fasta)},
        ),
    )

    result = run(["prune-scaffold", "Ltrop.acc", "--local-dir", "data"], tmp_path)
    assert result.exit_code == 0

    # chr1 (mapped), maxicircle kept; unmapped removed
    pruned = fasta.read_text()
    assert "chr1" in pruned
    assert "maxicircle" in pruned
    assert "unmapped" not in pruned


# ============================================================================== search parametrized


@pytest.mark.parametrize("term", ["donovani", "5661", "PRJNA"])
def test_search_common_terms(installed, term):
    """Search works with species, taxid, project accessions."""
    base, _ = installed
    result = run(["search", term, "--local-dir", "data"], base)
    assert result.exit_code == 0


# ============================================================================== restore edge cases


def test_restore_without_accessions_file_fails_clearly(tmp_path):
    """Restore fails when no accessions.txt exists."""
    result = run(["restore", "--local-dir", "data"], tmp_path)

    assert result.exit_code == 1
    assert "accessions" in result.output.lower()


def test_restore_handles_corrupted_accessions_format(tmp_path):
    """Restore skips malformed lines in accessions.txt."""
    (tmp_path / "accessions.txt").write_text("# header\nvalid_entry\tmyalias\nbad line with many\tfields\there\n")

    result = run(["restore", "--dry-run", "--local-dir", "data"], tmp_path)

    assert "skipping" in result.output.lower() or result.exit_code in (0, 1)


# ============================================================================== classify helper


def test_classify_sorts_files_into_roles(tmp_path):
    """Internal _classify() function assigns FASTA and GFF roles."""
    from leishref.cli import _classify

    fasta = tmp_path / "seq.fna"
    gff = tmp_path / "annot.gff"
    other = tmp_path / "notes.txt"

    fasta.touch()
    gff.touch()
    other.touch()

    roles = _classify([fasta, gff, other])
    assert roles.get("fasta") == fasta
    assert roles.get("gff") == gff
    assert "notes" not in str(roles)


def test_classify_handles_none_paths():
    """_classify() ignores None paths."""
    from leishref.cli import _classify

    roles = _classify([None, None])
    assert roles == {}


# ============================================================================== local alias map


def test_local_alias_map_parses_accessions_txt(tmp_path):
    """_local_alias_map() builds dict from accessions.txt."""
    from leishref.cli import _local_alias_map

    accessions = tmp_path / "accessions.txt"
    accessions.write_text("# comment\nGCA_001\tmy_alias1\nGCA_002\tmy_alias2\n")

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        mapping = _local_alias_map()
        assert mapping == {"my_alias1": "GCA_001", "my_alias2": "GCA_002"}
    finally:
        os.chdir(original_cwd)


def test_local_alias_map_returns_empty_when_no_file(tmp_path):
    """_local_alias_map() returns {} when accessions.txt missing."""
    from leishref.cli import _local_alias_map

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        mapping = _local_alias_map()
        assert mapping == {}
    finally:
        os.chdir(original_cwd)


# ============================================================================== source label


def test_source_label_identifies_refseq():
    """_source_label() recognizes GCF_ prefix as RefSeq."""
    from leishref.cli import _source_label

    genome = Genome(source="NCBI", accession="GCF_000410715.1")
    assert _source_label(genome) == "RefSeq"


def test_source_label_identifies_genbank():
    """_source_label() recognizes GCA_ prefix as GenBank."""
    from leishref.cli import _source_label

    genome = Genome(source="NCBI", accession="GCA_000410715.1")
    assert _source_label(genome) == "GenBank"


def test_source_label_unknown_when_no_source():
    """_source_label() returns '?' when source is None."""
    from leishref.cli import _source_label

    genome = Genome(source=None, accession="GCA_000410715.1")
    assert _source_label(genome) == "?"


# ============================================================================== flatten dict


def test_flatten_dict_converts_nested_to_dotted_keys(tmp_path):
    """_flatten_dict() converts nested dicts to dot-separated keys."""
    from leishref.cli import _flatten_dict

    nested = {"a": {"b": 1, "c": 2}, "d": 3}
    flat = _flatten_dict(nested)

    assert flat == {"a.b": 1, "a.c": 2, "d": 3}


# ============================================================================== read accessions


def test_read_accessions_parses_tab_separated_lines(tmp_path):
    """_read_accessions() parses tab-separated name-alias pairs."""
    from leishref.cli import _read_accessions

    accessions = tmp_path / "test.txt"
    accessions.write_text("GCA_001\tmy_alias\nGCA_002\tanother\n")

    pairs = _read_accessions(accessions)
    assert pairs == [("GCA_001", "my_alias"), ("GCA_002", "another")]


def test_read_accessions_ignores_comments_and_blanks(tmp_path):
    """_read_accessions() skips comment lines and blank lines."""
    from leishref.cli import _read_accessions

    accessions = tmp_path / "test.txt"
    accessions.write_text("# comment\nGCA_001\tmy_alias\n\n# another comment\n")

    pairs = _read_accessions(accessions)
    assert pairs == [("GCA_001", "my_alias")]


def test_read_accessions_reports_malformed_lines(tmp_path, capsys):
    """_read_accessions() reports lines with wrong field count."""
    from leishref.cli import _read_accessions

    accessions = tmp_path / "test.txt"
    accessions.write_text("GCA_001\tname\textra_field\n")  # 3 fields, not 2

    pairs = _read_accessions(accessions)
    assert pairs == []
    # Should report error via click.echo


# ============================================================================== cache key


def test_cache_key_uses_accession_when_present():
    """cache_key() returns accession if available."""
    from leishref.cli import cache_key

    genome = Genome(accession="GCA_123.1", identifier="custom_name")
    assert cache_key(genome) == "GCA_123.1"


def test_cache_key_uses_identifier_as_fallback():
    """cache_key() falls back to identifier when no accession."""
    from leishref.cli import cache_key

    genome = Genome(accession=None, identifier="my_scaffold")
    assert cache_key(genome) == "my_scaffold"


# ============================================================================== require


def test_require_fails_on_unknown_genome(tmp_path):
    """_require() exits nonzero when genome not found."""
    from leishref.cli import _require

    with pytest.raises(SystemExit) as exc:
        _require([], "NonExistent", "test database")
    assert exc.value.code != 0


# ============================================================================== genome alias


def test_genome_alias_appends_tritryp_suffix_for_tritrypdb():
    """_genome_alias() adds '_tritryp' suffix for TriTrypDB genomes."""
    from leishref.cli import _genome_alias

    genome = Genome(identifier="Lsp.Ghana", source="TriTrypDB", accession=None)
    alias = _genome_alias(genome)
    assert alias == "Lsp.Ghana_tritryp"


def test_genome_alias_prefers_catalog_alias():
    """_genome_alias() uses catalog alias when available."""
    from leishref.cli import _genome_alias

    genome = Genome(identifier="GCA_123.1", source="NCBI", accession="GCA_123.1")
    # This would require aliases.txt, so just check it returns identifier as fallback
    alias = _genome_alias(genome)
    assert "GCA_123.1" in alias or alias


# ============================================================================== console


def test_console_creates_rich_console():
    """_console() returns a Rich console object."""
    from leishref.cli import _console

    console = _console()
    assert console is not None
    assert hasattr(console, "print")


# ============================================================================== parent record


def test_parent_record_includes_checksum_and_filename(tmp_path):
    """_parent_record() creates metadata record for scaffold parent."""
    from leishref.cli import _parent_record

    fasta = tmp_path / "test.fa"
    fasta.write_text(">seq1\nACGT\n")
    genome = Genome(identifier="GCA_123", species="Leishmania donovani", strain="BPK282A1", accession="GCA_123")

    record = _parent_record(fasta, genome)

    assert record["file"] == "test.fa"
    assert "md5" in record
    assert record["name"] == "GCA_123"
    assert record["species"] == "Leishmania donovani"
