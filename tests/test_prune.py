"""Scaffold pruning: keep mapped chromosomes plus anything kinetoplast-like."""

from leishref.prune import is_kinetoplast, prune_fasta


def test_is_kinetoplast_matches_known_patterns():
    for name in ("kinetoplast", "maxicircle", "maxi_1", "mitochondrion", "mitochondrial_dna", "mtDNA", "mt_dna_1"):
        assert is_kinetoplast(name), name


def test_is_kinetoplast_rejects_unrelated_names():
    assert not is_kinetoplast("chromosome1")
    assert not is_kinetoplast("NW_012345.1")


def test_prune_fasta_keeps_only_mapped_and_kinetoplast_sequences(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">chr1\nACGT\n>unmapped_contig\nTTTT\n>maxicircle\nGGGG\n")

    pruned = prune_fasta(fasta, {"chr1"})

    assert pruned == ">chr1\nACGT\n>maxicircle\nGGGG\n"


def test_prune_fasta_drops_everything_when_nothing_matches(tmp_path):
    fasta = tmp_path / "assembly.fa"
    fasta.write_text(">unmapped\nACGT\n")

    assert prune_fasta(fasta, {"chr1"}) == ""
