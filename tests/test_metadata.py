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
    (directory / "metadata.yaml").write_text("source: Local\n")

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


def test_a_checksum_is_never_recorded_without_the_file_it_belongs_to():
    """Entries imported from NCBI's summary have neither yet; having one without the
    other would mean verify could not tell what it was checking."""
    for genome in catalog():
        for kind in ("fasta", "gff"):
            if genome.checksums.get(kind):
                assert genome.files.get(kind), f"{genome.identifier}: {kind} checksum but no filename"


def test_entries_that_name_files_are_downloadable():
    for genome in catalog():
        if genome.fasta:
            assert genome.accession or genome.zenodo_doi, f"{genome.identifier} names a file but has no source"


def test_haystack_covers_identity_and_provenance(genome):
    genome.provenance = {"bioproject": "PRJNA450813", "zenodo_doi": "10.5281/zenodo.1"}
    hay = genome.haystack()

    for expected in ("gca_1.1", "leishmania tropica", "5666", "g.fna", "prjna450813", "zenodo"):
        assert expected in hay


def test_matches_is_case_insensitive(genome):
    assert genome.matches(["TROPICA"])
    assert genome.matches(["tropica"])


def test_multiple_terms_narrow_rather_than_widen(genome):
    genome.provenance = {"zenodo_doi": "10.5281/zenodo.1"}
    assert genome.matches(["tropica", "zenodo"])
    assert not genome.matches(["tropica", "donovani"])


def test_matches_finds_taxon_id_given_as_text(genome):
    assert genome.matches(["5666"])


def test_a_lone_star_matches_every_genome(genome):
    assert genome.matches(["*"])


def test_wildcards_match_within_a_term(genome):
    assert genome.matches(["GCA_1*"])
    assert genome.matches(["L*tropica"])
    assert genome.matches(["gca_?.1"])
    assert not genome.matches(["GCF_*"])


def test_wildcard_terms_narrow_like_plain_terms(genome):
    genome.provenance = {"zenodo_doi": "10.5281/zenodo.1"}
    assert genome.matches(["*tropica", "zenodo"])
    assert not genome.matches(["*tropica", "donov*"])


def test_a_term_without_wildcards_stays_a_substring_match(genome):
    """'[' and friends only switch on globbing when the user actually types them."""
    assert genome.matches(["tropic"])
    assert not genome.matches(["tropicaX"])


def test_every_catalog_genome_has_statistics():
    for entry in catalog():
        assert entry.stats.get("num_bases"), f"{entry.identifier} has no num_bases"


def test_catalog_sources_come_from_a_known_vocabulary():
    """source says where `download` fetches a genome from, not who assembled it."""
    allowed = {"NCBI", "Zenodo", "TriTrypDB", "Local", "Leishref", "Custom"}
    for entry in catalog():
        assert entry.source in allowed, f"{entry.identifier} has source {entry.source!r}"


def test_zenodo_sourced_genomes_carry_a_doi():
    for entry in catalog():
        if entry.source == "Zenodo":
            assert entry.zenodo_doi, f"{entry.identifier} is sourced from Zenodo but has no DOI"


def test_contigs_are_never_fewer_than_scaffolds():
    """A scaffold holds at least one contig, so the counts can only go one way."""
    for entry in catalog():
        assert entry.stats["num_contigs"] >= entry.stats["num_scaffolds"], entry.identifier


def test_ungapped_length_never_exceeds_total():
    for entry in catalog():
        assert entry.stats["num_ungapped"] <= entry.stats["num_bases"], entry.identifier


def test_contig_n50_never_exceeds_scaffold_n50():
    for entry in catalog():
        assert entry.stats["contig_n50"] <= entry.stats["scaffold_n50"], entry.identifier


def test_ncbi_entries_record_assembly_level_and_release_date():
    for entry in catalog():
        if entry.source == "NCBI":
            assert entry.assembly_level, f"{entry.identifier} has no assembly_level"
            assert entry.release_date, f"{entry.identifier} has no release_date"


def test_assembly_levels_come_from_a_known_vocabulary():
    allowed = {"Complete Genome", "Chromosome", "Scaffold", "Contig"}
    for entry in catalog():
        if entry.assembly_level:
            assert entry.assembly_level in allowed, f"{entry.identifier}: {entry.assembly_level!r}"


def test_most_genomes_name_their_strain():
    """Not every submitter registers one, so this is a proportion rather than a count."""
    entries = catalog()
    named = [g for g in entries if g.strain]
    assert len(named) >= 0.7 * len(entries)


def test_strain_is_taken_from_the_organism_name_when_ncbi_leaves_it_empty():
    """An infraspecific taxon carries its strain in organism_name and nowhere else."""
    from leishref.ncbi import strain_from_organism

    assert strain_from_organism("Leishmania infantum JPCM5") == "JPCM5"
    assert strain_from_organism("Leishmania braziliensis MHOM/BR/75/M2904") == "MHOM/BR/75/M2904"
    assert strain_from_organism("Leishmania infantum") == ""
    assert strain_from_organism("Leishmania sp. Ghana") == ""
    assert strain_from_organism(None) == ""


def test_catalog_entries_are_grouped_by_origin():
    """Every shipped entry sits in the subdirectory its origin calls for."""
    from leishref.metadata import CATALOG_DIR, catalog_group

    for entry in catalog():
        assert entry.path.parent.name == catalog_group(entry), entry.identifier
        assert entry.path.parent.parent == CATALOG_DIR, entry.identifier


def test_grouping_follows_how_a_genome_was_made(genome):
    """Publishing a scaffold on Zenodo must not move it out of scaffold/."""
    from leishref.metadata import catalog_group

    genome.scaffold = {"reference": {"name": "GCA_1.1"}}
    genome.source = "Zenodo"
    genome.provenance = {"zenodo_doi": "10.5281/zenodo.1"}
    assert catalog_group(genome) == "scaffolds"


def test_an_accession_decides_the_ncbi_group(genome):
    from leishref.metadata import catalog_group

    genome.accession = "GCF_000002875.2"
    assert catalog_group(genome) == "ncbi"
    genome.accession = "GCA_000002875.2"
    assert catalog_group(genome) == "ncbi"


def test_a_genome_with_no_origin_at_all_is_local(genome):
    from leishref.metadata import catalog_group

    genome.accession = None
    genome.source = "Local"
    genome.provenance = {}
    assert catalog_group(genome) == "local"


def test_a_flat_directory_is_still_read(tmp_path):
    """Local databases are flat, and a catalog written before grouping stays readable."""
    from leishref.metadata import catalog as read_catalog

    write_genome(tmp_path / "flat", Genome(identifier="flat", species="Leishmania donovani"))
    write_genome(tmp_path / "ncbi" / "GCA_1.1", Genome(identifier="GCA_1.1", accession="GCA_1.1"))

    found = {entry.identifier for entry in read_catalog(tmp_path)}
    assert found == {"flat", "GCA_1.1"}
