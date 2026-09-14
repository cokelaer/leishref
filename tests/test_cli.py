"""Command-line behaviour that does not need the network."""

import os
from pathlib import Path

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


def test_download_requires_an_alias(tmp_path):
    result = run(["download", "GCA_000410715.1"], tmp_path)
    assert result.exit_code != 0
    assert "--alias" in result.output


def test_user_and_dev_commands_are_separated():
    result = CliRunner().invoke(cli, ["--help"])
    assert "download" in result.output
    assert "dev" in result.output
    assert "publish" not in result.output, "maintainer commands belong under dev"

    dev = CliRunner().invoke(cli, ["dev", "--help"])
    for command in ("fetch", "add", "scaffold", "publish", "derive-agp"):
        assert command in dev.output


def test_verify_passes_on_an_intact_database(installed):
    base, _ = installed
    result = run(["verify"], base)
    assert result.exit_code == 0
    assert "mismatch: 0" in result.output


def test_verify_fails_when_a_file_changed(installed):
    base, fasta = installed
    fasta.write_text(">c1\nTTTTTTTT\n")

    result = run(["verify"], base)
    assert result.exit_code == 1
    assert "CHECKSUM MISMATCH" in result.output


def test_verify_reports_a_missing_file(installed):
    base, fasta = installed
    fasta.unlink()

    result = run(["verify"], base)
    assert result.exit_code == 1
    assert "MISSING" in result.output


def test_link_creates_alias_named_symlinks(installed):
    base, _ = installed
    result = run(["link"], base)

    link = base / "Ltrop.flye.fa"
    assert result.exit_code == 0
    assert link.is_symlink()
    assert link.read_text() == ">c1\nACGTACGT\n"


def test_info_lists_catalog_and_local(installed):
    base, _ = installed
    result = run(["info"], base)

    assert "Catalog:" in result.output
    assert "Local: 1 installed" in result.output
    assert "Ltrop.flye" in result.output


def test_info_on_an_unknown_name_fails_clearly(installed):
    base, _ = installed
    result = run(["info", "nonexistent"], base)

    assert result.exit_code == 1
    assert "Not in catalog" in result.output


def test_search_finds_by_species(installed):
    base, _ = installed
    result = run(["search", "donovani"], base)

    assert result.exit_code == 0
    assert "GCA_000227135.2" in result.output
    assert all("donovani" in line for line in result.output.splitlines() if line.startswith("  "))


def test_search_narrows_with_more_terms(installed):
    base, _ = installed
    broad = run(["search", "tropica"], base)
    narrow = run(["search", "tropica", "zenodo"], base)

    assert broad.exit_code == narrow.exit_code == 0
    assert int(narrow.output.split()[0]) < int(broad.output.split()[0])


def test_search_matches_taxon_id(installed):
    base, _ = installed
    result = run(["search", "5661"], base)
    assert result.exit_code == 0
    assert "donovani" in result.output


def test_search_without_a_match_exits_nonzero(installed):
    base, _ = installed
    result = run(["search", "xyzzy"], base)

    assert result.exit_code == 1
    assert "No genome matches" in result.output


def test_search_requires_a_term(installed):
    base, _ = installed
    assert run(["search"], base).exit_code != 0


def test_search_flags_installed_genomes(tmp_path):
    """A local install records its origin, so search can say it is already present."""
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

    result = run(["search", origin.identifier], tmp_path)
    assert "installed as mine" in result.output
