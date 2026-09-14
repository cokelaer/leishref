"""Genome statistics computed in a single pass."""

import pytest

from leishref.checksums import genome_stats, md5_file


def write(tmp_path, seqs):
    path = tmp_path / "g.fa"
    with open(path, "w") as fh:
        for name, seq in seqs.items():
            fh.write(f">{name}\n")
            for i in range(0, len(seq), 60):
                fh.write(seq[i : i + 60] + "\n")
    return path


def test_counts_bases_scaffolds_and_contigs(tmp_path):
    stats = genome_stats(write(tmp_path, {"a": "ACGT" * 10, "b": "ACGT" * 5}))
    assert stats["num_bases"] == 60
    assert stats["num_scaffolds"] == 2
    assert stats["num_contigs"] == 2, "gapless records are one contig each"


def test_a_gapped_scaffold_holds_several_contigs(tmp_path):
    """The distinction the record count hides: one chromosome, many contigs."""
    stats = genome_stats(write(tmp_path, {"chr1": "A" * 100 + "N" * 50 + "C" * 100 + "N" * 50 + "G" * 100}))
    assert stats["num_scaffolds"] == 1
    assert stats["num_contigs"] == 3
    assert stats["num_gaps"] == 2


def test_gc_excludes_ambiguous_bases(tmp_path):
    """Counting N in the denominator deflates GC for gappy assemblies."""
    stats = genome_stats(write(tmp_path, {"a": "GC" + "N" * 98}))
    assert stats["gc_percent"] == 100.0
    assert stats["num_ambiguous"] == 98


def test_gc_of_a_balanced_sequence(tmp_path):
    assert genome_stats(write(tmp_path, {"a": "ACGT" * 25}))["gc_percent"] == 50.0


def test_n50_is_the_sequence_spanning_half_the_assembly(tmp_path):
    # 100 + 50 + 30 + 20 = 200; half is 100, reached by the first sequence
    stats = genome_stats(write(tmp_path, {"a": "A" * 100, "b": "C" * 50, "c": "G" * 30, "d": "T" * 20}))
    assert stats["scaffold_n50"] == 100
    assert stats["scaffold_l50"] == 1


def test_l50_counts_how_many_sequences_reach_half(tmp_path):
    # 60 + 50 + 40 = 150; half is 75, reached only after the second sequence
    stats = genome_stats(write(tmp_path, {"a": "A" * 60, "b": "C" * 50, "c": "G" * 40}))
    assert stats["scaffold_n50"] == 50
    assert stats["scaffold_l50"] == 2


def test_contig_and_scaffold_n50_differ_on_a_gapped_assembly(tmp_path):
    stats = genome_stats(write(tmp_path, {"chr1": "A" * 500 + "N" * 50 + "C" * 500}))
    assert stats["scaffold_n50"] == 1050
    assert stats["contig_n50"] == 500


def test_gaps_count_runs_not_bases(tmp_path):
    stats = genome_stats(write(tmp_path, {"a": "ACGT" + "N" * 30 + "ACGT" + "N" * 10 + "ACGT"}))
    assert stats["num_gaps"] == 2
    assert stats["num_ambiguous"] == 40


def test_short_n_runs_are_ambiguous_bases_not_gaps(tmp_path):
    """NCBI's rule: a run shorter than min_gap sits inside a contig rather than splitting it."""
    stats = genome_stats(write(tmp_path, {"a": "ACGT" + "N" * 5 + "ACGT"}))
    assert stats["num_gaps"] == 0
    assert stats["num_contigs"] == 1
    assert stats["num_ambiguous"] == 5, "still counted as ambiguous"
    assert stats["num_ungapped"] == stats["num_bases"], "and not deducted as gap length"


def test_min_gap_is_adjustable(tmp_path):
    path = write(tmp_path, {"a": "ACGT" + "N" * 5 + "ACGT"})
    assert genome_stats(path, min_gap=1)["num_gaps"] == 1
    assert genome_stats(path, min_gap=10)["num_gaps"] == 0


def test_gap_runs_are_not_double_counted_across_lines(tmp_path):
    """A 200-base gap spans several wrapped lines but is still one gap."""
    stats = genome_stats(write(tmp_path, {"a": "ACGT" + "N" * 200 + "ACGT"}))
    assert stats["num_gaps"] == 1


def test_gaps_do_not_carry_over_between_records(tmp_path):
    stats = genome_stats(write(tmp_path, {"a": "AC" + "N" * 20, "b": "N" * 20 + "GT"}))
    assert stats["num_gaps"] == 2


def test_gapless_assembly_reports_no_gaps(tmp_path):
    stats = genome_stats(write(tmp_path, {"a": "ACGT" * 25}))
    assert stats["num_gaps"] == 0
    assert stats["num_ambiguous"] == 0
    assert stats["num_ungapped"] == stats["num_bases"]


def test_ungapped_length_deducts_gap_bases_only(tmp_path):
    stats = genome_stats(write(tmp_path, {"a": "A" * 100 + "N" * 50 + "C" * 100}))
    assert stats["num_bases"] == 250
    assert stats["num_ungapped"] == 200


def test_empty_fasta_does_not_divide_by_zero(tmp_path):
    path = tmp_path / "empty.fa"
    path.write_text("")
    stats = genome_stats(path)
    assert stats["num_bases"] == 0
    assert stats["num_contigs"] == 0
    assert stats["num_scaffolds"] == 0
    assert stats["gc_percent"] == 0.0
    assert stats["scaffold_n50"] == 0
    assert stats["contig_n50"] == 0


def test_md5_matches_known_content(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("hello")
    assert md5_file(path) == "5d41402abc4b2a76b9719d911017c592"
