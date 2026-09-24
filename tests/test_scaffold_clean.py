"""Test AGP parsing and scaffold cleaning."""

import tempfile
from pathlib import Path

import pytest

from leishref.scaffold import clean_scaffolded_fasta, parse_agp, trim_ragtag_suffix


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


def test_clean_scaffolded_fasta_custom_patterns():
    """Clean fasta with custom keep_patterns."""
    fasta_content = """>contig1
ACGT
>kinetoplast_extra
GCTA
>custom_pattern
TTTT
"""

    agp_content = """chr1\t1\t4\t1\tD\tcontig1\t1\t4\t+
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        fasta_path = Path(tmpdir) / "test.fasta"
        agp_path = Path(tmpdir) / "test.agp"
        fasta_path.write_text(fasta_content)
        agp_path.write_text(agp_content)

        result = clean_scaffolded_fasta(fasta_path, agp_path, keep_patterns=["custom"])

        assert "contig1" in result
        assert "custom_pattern" in result
        assert "kinetoplast_extra" not in result


def test_trim_ragtag_suffix():
    """Trim _RagTag suffix from FASTA headers."""
    fasta_content = """>chr1_RagTag
ACGT
>chr2_RagTag
GCTA
>chr3
TTTT
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        fasta_path = Path(tmpdir) / "test.fasta"
        fasta_path.write_text(fasta_content)

        result = trim_ragtag_suffix(fasta_path)

        assert ">chr1\n" in result
        assert ">chr2\n" in result
        assert ">chr3\n" in result
        assert "_RagTag" not in result


def test_parse_agp_ignores_gaps():
    """Parse AGP ignores gap (N) entries."""
    agp_content = """chr1\t1\t5000\t1\tD\tcontig1\t1\t5000\t+
chr1\t5001\t5100\t2\tN\t100\t100\tyes\tcontig
chr1\t5101\t10000\t3\tD\tcontig2\t1\t4900\t+
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        agp_path = Path(tmpdir) / "test.agp"
        agp_path.write_text(agp_content)

        placements = parse_agp(agp_path)

        # Should have contig1 and contig2, but not the gap
        assert "contig1" in placements
        assert "contig2" in placements
        assert len(placements) == 2


def test_parse_agp_handles_comments():
    """Parse AGP skips comment lines and blank lines."""
    agp_content = """# This is a comment
chr1\t1\t5000\t1\tD\tcontig1\t1\t5000\t+

# Another comment
chr1\t5001\t10000\t2\tD\tcontig2\t1\t5000\t+
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        agp_path = Path(tmpdir) / "test.agp"
        agp_path.write_text(agp_content)

        placements = parse_agp(agp_path)

        assert len(placements) == 2
        assert "contig1" in placements
        assert "contig2" in placements


def test_parse_agp_malformed_lines():
    """Parse AGP skips malformed lines."""
    agp_content = """chr1\t1\t5000\t1\tD\tcontig1\t1\t5000\t+
malformed line without tabs
chr1\t5001\t10000\t2\tD\tcontig2\t1\t5000\t+
chr1\ttoo\tfew\tfields
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        agp_path = Path(tmpdir) / "test.agp"
        agp_path.write_text(agp_content)

        placements = parse_agp(agp_path)

        # Should parse only valid lines
        assert len(placements) == 2
        assert "contig1" in placements
        assert "contig2" in placements
