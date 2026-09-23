"""Chromosome name mapping and sequence renaming, exercised directly (no CLI)."""

from leishref.chromosomes import (
    detect_sequences_from_fasta,
    get_chromosome_info,
    load_chromosome_map,
    rename_fasta_sequences,
    save_chromosome_map,
)


def test_load_chromosome_map_missing_file_returns_empty(tmp_path):
    assert load_chromosome_map(tmp_path) == {}


def test_save_and_load_chromosome_map_roundtrip(tmp_path):
    mapping = {"acc1": [{"accession": "c1", "index": 1, "name": "c1"}]}
    save_chromosome_map(mapping, tmp_path)

    assert (tmp_path / "chromosome_map.yaml").exists()
    assert load_chromosome_map(tmp_path) == mapping


def test_get_chromosome_info_returns_empty_for_unknown_accession(tmp_path):
    assert get_chromosome_info("nope", tmp_path) == []


def test_detect_sequences_from_fasta_marks_37th_as_maxicircle(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text("".join(f">seq{i}\nACGT\n" for i in range(1, 39)))

    sequences = detect_sequences_from_fasta(fasta)

    assert len(sequences) == 38
    assert sequences[36]["accession"] == "seq37"
    assert sequences[36]["type"] == "maxicircle"
    assert "type" not in sequences[0]
    assert "type" not in sequences[37]


def test_rename_fasta_sequences_reports_when_fasta_has_no_headers(tmp_path):
    fasta = tmp_path / "empty.fa"
    fasta.write_text("ACGTACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert name_map == {}
    assert "No sequences found" in error


def test_rename_fasta_sequences_auto_detects_and_persists_the_map(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGT\n>c2\nTTTT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "myacc", "number", tmp_path)

    assert error is None
    assert name_map == {"c1": "1", "c2": "2"}
    assert ">1\nACGT\n>2\nTTTT\n" == content

    # Auto-detection is persisted, so a second call reuses it instead of re-detecting
    assert get_chromosome_info("myacc", tmp_path) == [
        {"accession": "c1", "name": "c1", "index": 1},
        {"accession": "c2", "name": "c2", "index": 2},
    ]


def test_rename_fasta_sequences_contig_ids_are_never_renamed(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">NW_012345.1\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert error is None
    assert name_map == {"NW_012345.1": "NW_012345.1"}
    assert ">NW_012345.1\nACGT\n" in content


def test_rename_fasta_sequences_maxicircle_flavor_override(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c37\nACGT\n")
    save_chromosome_map({"acc": [{"accession": "c37", "name": "c37", "index": 1, "type": "maxicircle"}]}, tmp_path)

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "number", tmp_path)

    assert error is None
    assert name_map == {"c37": "maxicircle"}
    assert ">maxicircle\nACGT\n" in content


def test_rename_fasta_sequences_name_flavor_uses_stored_name(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">c1\nACGT\n")
    save_chromosome_map({"acc": [{"accession": "c1", "name": "chr I", "index": 1}]}, tmp_path)

    content, name_map, error = rename_fasta_sequences(fasta, "acc", "name", tmp_path)

    assert error is None
    assert name_map == {"c1": "chr I"}
    assert ">chr I\nACGT\n" in content


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
