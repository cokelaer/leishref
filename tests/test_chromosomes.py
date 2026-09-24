"""Chromosome name mapping and sequence renaming, exercised directly (no CLI)."""

import csv

from leishref.chromosomes import (
    detect_sequences_from_fasta,
    get_chromosome_info,
    load_chromosome_map,
    rename_fasta_sequences,
)


def test_load_chromosome_map_missing_file_returns_empty(tmp_path):
    assert load_chromosome_map(tmp_path) == {}


def test_load_chromosome_map_from_csv(tmp_path):
    csv_file = tmp_path / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "c1", "chromosome": "1", "taxid": "", "origin": "GCA_001"})

    mapping = load_chromosome_map(tmp_path)

    assert mapping == {"c1": {"chromosome": "1", "taxid": "", "origin": "GCA_001"}}


def test_get_chromosome_info_returns_none_for_unknown_accession(tmp_path):
    assert get_chromosome_info("nope", tmp_path) is None


def test_detect_sequences_from_fasta_returns_sequence_ids(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">seq1\nACGT\n>seq2\nTTTT\n>seq3\nGGGG\n")

    sequences = detect_sequences_from_fasta(fasta)

    assert sequences == ["seq1", "seq2", "seq3"]


def test_rename_fasta_sequences_reports_when_fasta_has_no_headers(tmp_path):
    fasta = tmp_path / "empty.fa"
    fasta.write_text("ACGTACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert name_map == {}
    assert "No sequences found" in error


def test_rename_fasta_sequences_number_flavor_renames_by_order(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGT\n>c2\nTTTT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "myacc", "number", tmp_path)

    assert error is None
    assert name_map == {"c1": "1", "c2": "2"}
    assert ">1\nACGT\n>2\nTTTT\n" == content


def test_rename_fasta_sequences_contig_ids_are_never_renamed(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">NW_012345.1\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert error is None
    assert name_map == {"NW_012345.1": "NW_012345.1"}
    assert ">NW_012345.1\nACGT\n" in content


def test_rename_fasta_sequences_kraken_without_taxid_errors(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "kraken", tmp_path, taxon_id=None)

    assert name_map == {}
    assert "requires --taxid" in error


def test_rename_fasta_sequences_unknown_flavor_keeps_original_name(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "bogus", tmp_path)

    assert error is None
    assert name_map == {"c1": "c1"}


def test_rename_fasta_sequences_header_description_is_dropped(tmp_path):
    """A header with a description after the ID keeps only the new ID."""
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1 some description here\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert error is None
    assert ">1\nACGT\n" in content
    assert "description" not in content


def test_rename_fasta_sequences_preserves_sequence_data(tmp_path):
    """Regression: the header regex must never swallow the following sequence line."""
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGTACGTACGT\n>c2\nTTTTGGGGCCCC\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert error is None
    assert content == ">1\nACGTACGTACGT\n>2\nTTTTGGGGCCCC\n"
