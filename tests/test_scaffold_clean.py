"""Test AGP parsing and scaffold cleaning."""

import tempfile
from pathlib import Path

import pytest

from leishdb.scaffold import clean_scaffolded_fasta, parse_agp


def test_parse_agp():
    """Parse AGP file and extract contig placements."""
    agp_content = """chr1\t1\t5000\t1\tD\tcontig1\t1\t5000\t+
chr1\t5001\t10000\t2\tD\tcontig2\t1\t5000\t+
chr1\t10001\t10100\t3\tN\t100\t100\tyes\tcontig
chr2\t1\t3000\t1\tD\tcontig3\t1\t3000\t+
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        agp_path = Path(tmpdir) / "test.agp"
        agp_path.write_text(agp_content)

        placements = parse_agp(agp_path)
        assert "contig1" in placements
        assert "contig2" in placements
        assert "contig3" in placements
        assert placements["contig1"] == [(1, 5000, "chr1")]
        assert placements["contig2"] == [(5001, 10000, "chr1")]
        assert placements["contig3"] == [(1, 3000, "chr2")]


def test_clean_scaffolded_fasta():
    """Clean fasta to keep only chr-anchored + whitelist."""
    fasta_content = """>contig1 description
ACGTACGTACGTACGT
>contig2
NNNNNNNNNNNNNNNN
>maxicircle
GCTAGCTAGCTAGCTA
>unplaced_contig
TTTTTTTTTTTTTTTT
"""

    agp_content = """chr1\t1\t16\t1\tD\tcontig1\t1\t16\t+
chr1\t17\t32\t2\tD\tcontig2\t1\t16\t+
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        fasta_path = Path(tmpdir) / "test.fasta"
        agp_path = Path(tmpdir) / "test.agp"
        fasta_path.write_text(fasta_content)
        agp_path.write_text(agp_content)

        result = clean_scaffolded_fasta(fasta_path, agp_path)

        assert "contig1" in result
        assert "contig2" in result
        assert "maxicircle" in result
        assert "unplaced_contig" not in result
        assert "ACGTACGTACGTACGT" in result
        assert "GCTAGCTAGCTAGCTA" in result
