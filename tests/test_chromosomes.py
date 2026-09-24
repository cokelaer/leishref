"""Chromosome name mapping and sequence renaming, exercised directly (no CLI)."""

import csv

from leishref.chromosomes import (
    detect_sequences_from_fasta,
    extract_sequences_with_headers,
    get_chromosome_info,
    get_genome_sequences,
    get_taxid_from_species,
    load_chromosome_map,
    parse_chromosome_from_header,
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


def test_extract_sequences_with_headers(tmp_path):
    """Extract sequence ID and full header."""
    fasta = tmp_path / "test.fa"
    fasta.write_text(">seq1 description here\nACGT\n>seq2\nTTTT\n")

    seqs = extract_sequences_with_headers(fasta)

    assert len(seqs) == 2
    assert seqs[0]["accession"] == "seq1"
    assert "description here" in seqs[0]["header"]
    assert seqs[1]["accession"] == "seq2"


def test_parse_chromosome_from_header_with_leading_zeros(tmp_path):
    """Parse chromosome numbers and strip leading zeros."""
    assert parse_chromosome_from_header("chromosome 01") == "1"
    assert parse_chromosome_from_header("chromosome 02") == "2"
    assert parse_chromosome_from_header("chr 01") == "1"
    assert parse_chromosome_from_header("CHR28") == "28"


def test_parse_chromosome_from_header_not_found(tmp_path):
    """Return None when chromosome not found."""
    assert parse_chromosome_from_header("contig_001") is None
    assert parse_chromosome_from_header("scaffold") is None


def test_get_taxid_from_species_found(tmp_path):
    """Lookup taxid from species_taxon_mapping.yaml."""
    from pathlib import Path

    import yaml

    mapping_file = tmp_path / "species_taxon_mapping.yaml"
    mapping_file.write_text(
        yaml.dump(
            {
                "Leishmania tropica": {"primary": 5666},
                "Leishmania donovani": {"primary": 5661},
            }
        )
    )

    taxid = get_taxid_from_species("Leishmania tropica", tmp_path)
    assert taxid == 5666

    taxid = get_taxid_from_species("Leishmania donovani", tmp_path)
    assert taxid == 5661


def test_get_taxid_from_species_not_found(tmp_path):
    """Return None for unknown species."""
    taxid = get_taxid_from_species("Unknown species", tmp_path)
    assert taxid is None


def test_get_genome_sequences(tmp_path):
    """Get all sequences for a genome from chromosome map."""
    csv_file = tmp_path / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "c1", "chromosome": "1", "taxid": "5661", "origin": "GCA_001"})
        writer.writerow({"accession": "c2", "chromosome": "2", "taxid": "5661", "origin": "GCA_001"})
        writer.writerow({"accession": "c3", "chromosome": "1", "taxid": "5666", "origin": "GCA_002"})

    seqs = get_genome_sequences("GCA_001", tmp_path)
    assert len(seqs) == 2
    assert seqs[0]["accession"] == "c1"
    assert seqs[1]["accession"] == "c2"

    seqs = get_genome_sequences("GCA_002", tmp_path)
    assert len(seqs) == 1
    assert seqs[0]["accession"] == "c3"


def test_rename_fasta_sequences_uses_chromosome_map_when_available(tmp_path):
    """Mapped sequences use chromosome value, unmapped keep original."""
    # Create chromosome_map
    csv_file = tmp_path / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "seq1", "chromosome": "10", "taxid": "", "origin": "GCA_test"})

    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">seq1\nACGT\n>seq2_extra\nTTTT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "GCA_test", "number", tmp_path)

    assert error is None
    assert name_map == {"seq1": "10", "seq2_extra": "seq2_extra"}
    assert ">10\nACGT\n" in content
    assert ">seq2_extra\nTTTT\n" in content


def test_rename_fasta_sequences_kraken_with_chromosome_map(tmp_path):
    """Kraken flavor with chromosome map."""
    # Create chromosome_map
    csv_file = tmp_path / "chromosome_map.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession", "chromosome", "taxid", "origin"])
        writer.writeheader()
        writer.writerow({"accession": "seq1", "chromosome": "1", "taxid": "", "origin": "GCA_test"})

    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">seq1\nACGT\n")

    content, name_map, error = rename_fasta_sequences(fasta, "GCA_test", "kraken", tmp_path, taxon_id=5666)

    assert error is None
    assert name_map == {"seq1": "1|kraken:taxid|5666"}
    assert ">1|kraken:taxid|5666\n" in content
