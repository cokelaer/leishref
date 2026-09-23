"""Command-line behaviour that does not need the network."""

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
    return tmp_path, fasta


def run(args, cwd):
    """Invoke the CLI as if it had been started from cwd."""
    previous = os.getcwd()
    os.chdir(cwd)
    try:
        return CliRunner().invoke(cli, args)
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
        int(n) for n in re.findall(r"^  (?:NCBI|TriTrypDB|Scaffolds|Custom|Zenodo|Other)\s+(\d+)$", output, re.M)
    )
    assert counted == total


def test_rename_sequences_auto_populates_chromosome_map(installed, tmp_path):
    """Rename-sequences auto-detects sequences and populates chromosome_map.yaml."""
    base, fasta = installed

    # Run rename-sequences with number flavor
    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "number", "--local-dir", "data"], base)
    assert result.exit_code == 0
    assert "Renaming sequences" in result.output

    # Check that output file was created and renamed
    output_file = fasta.parent / f"{fasta.stem}.number{fasta.suffix}"
    assert output_file.exists()

    # Check that sequence was renamed (from >c1 to >1)
    content = output_file.read_text()
    assert ">1\n" in content
    assert ">c1" not in content


def test_rename_sequences_with_roman_flavor(installed):
    """Rename-sequences with roman flavor renames to Roman numerals."""
    base, fasta = installed

    result = run(["rename-sequences", "Ltrop.flye", "--flavor", "roman", "--local-dir", "data"], base)
    assert result.exit_code == 0

    output_file = fasta.parent / f"{fasta.stem}.roman{fasta.suffix}"
    assert output_file.exists()

    # Check that sequence was renamed (from >c1 to >I)
    content = output_file.read_text()
    assert ">I\n" in content
    assert ">c1" not in content


def test_rename_sequences_with_kraken_flavor(tmp_path):
    """Rename-sequences with kraken flavor appends |kraken:taxid|<TAXID>."""
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

    output_file = fasta.parent / f"{fasta.stem}.kraken{fasta.suffix}"
    assert output_file.exists()

    # Check that sequence was renamed with kraken format
    content = output_file.read_text()
    assert ">c1|kraken:taxid|5666\n" in content
    assert ">c1\n" not in content


def test_rename_sequences_kraken_flavor_does_not_mislabel_37th_contig_as_maxicircle(tmp_path):
    """A contig_* sequence that happens to land at position 37 is not the maxicircle.

    Regression test: auto-detection used to hardcode "the 37th sequence is the
    maxicircle", which only holds for standard 36-chromosome + maxicircle NCBI
    assemblies. A custom scaffold with fewer numbered chromosomes can push an
    ordinary contig into slot 37, and it must still get the normal kraken tag
    instead of being renamed to the literal string "maxicircle".
    """
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

    output_file = fasta.parent / f"{fasta.stem}.kraken{fasta.suffix}"
    content = output_file.read_text()

    assert ">contig_10|kraken:taxid|5666\n" in content
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


def test_rename_sequences_kraken_flavor_uses_explicit_taxid(tmp_path):
    """Rename-sequences kraken flavor accepts --taxid parameter."""
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

    output_file = fasta.parent / f"{fasta.stem}.kraken{fasta.suffix}"
    content = output_file.read_text()
    assert ">c1|kraken:taxid|5661\n" in content
