"""Per-genome metadata directories."""

from pathlib import Path

import pytest
import yaml

from leishref.metadata import CATALOG_DIR, Genome, catalog, find, iter_genomes, read_genome, write_genome


@pytest.fixture
def genome():
    return Genome(
        identifier="GCA_1.1",
        source="NCBI",
        accession="GCA_1.1",
        taxon_id=5666,
        species="Leishmania tropica",
        files={"fasta": "g.fna", "gff": "g.gff"},
        checksums={"fasta": "aaa", "gff": "bbb"},
        stats={"num_bases": 100, "num_contigs": 2, "gc_percent": 59.7},
        date_added="2026-09-14",
    )


def test_roundtrip(tmp_path, genome):
    write_genome(tmp_path / "GCA_1.1", genome)
    loaded = read_genome(tmp_path / "GCA_1.1")

    assert loaded.identifier == "GCA_1.1"
    assert loaded.taxon_id == 5666
    assert loaded.files == {"fasta": "g.fna", "gff": "g.gff"}
    assert loaded.stats["gc_percent"] == 59.7


def test_empty_fields_are_not_written(tmp_path, genome):
    """An unset strain should be absent, not a null line of noise."""
    written = write_genome(tmp_path / "GCA_1.1", genome)
    data = yaml.safe_load(written.read_text())

    assert "strain" not in data
    assert "scaffold" not in data
    assert data["species"] == "Leishmania tropica"


def test_identifier_defaults_to_directory_name(tmp_path):
    directory = tmp_path / "Ltrop.flye"
    directory.mkdir()
    (directory / "metadata.yaml").write_text("source: MyAssembly\n")

    assert read_genome(directory).identifier == "Ltrop.flye"


def test_unknown_keys_are_ignored(tmp_path):
    """A newer catalog must not break an older install."""
    directory = tmp_path / "x"
    directory.mkdir()
    (directory / "metadata.yaml").write_text("identifier: x\nfuture_field: 1\n")

    assert read_genome(directory).identifier == "x"


def test_iter_genomes_skips_directories_without_metadata(tmp_path, genome):
    write_genome(tmp_path / "good", genome)
    (tmp_path / "empty").mkdir()
    (tmp_path / "loose.txt").write_text("x")

    assert [g.identifier for g in iter_genomes(tmp_path)] == ["GCA_1.1"]


def test_iter_genomes_on_missing_root_is_empty(tmp_path):
    assert list(iter_genomes(tmp_path / "absent")) == []


def test_file_paths_resolve_against_the_genome_directory(tmp_path, genome):
    write_genome(tmp_path / "g", genome)
    loaded = read_genome(tmp_path / "g")

    kinds = {kind: (path, md5) for kind, path, md5 in loaded.file_paths()}
    assert kinds["fasta"][0] == tmp_path / "g" / "g.fna"
    assert kinds["fasta"][1] == "aaa"


def test_find_matches_identifier_accession_or_filename(tmp_path, genome):
    write_genome(tmp_path / "GCA_1.1", genome)
    genomes = list(iter_genomes(tmp_path))

    assert find(genomes, "GCA_1.1") is not None
    assert find(genomes, "g.fna") is not None
    assert find(genomes, "nope") is None


def test_shipped_catalog_is_readable_and_populated():
    entries = catalog()
    assert entries, "the package must ship a catalog"
    assert all(g.identifier for g in entries)
    assert not (CATALOG_DIR / "manifest.csv").exists(), "the CSV manifest is gone"


def test_shipped_catalog_identifiers_are_unique():
    identifiers = [g.identifier for g in catalog()]
    assert len(set(identifiers)) == len(identifiers)


def test_shipped_catalog_records_files_and_checksums():
    for genome in catalog():
        assert genome.fasta, f"{genome.identifier} has no fasta recorded"
        assert genome.checksums.get("fasta"), f"{genome.identifier} has no fasta checksum"
