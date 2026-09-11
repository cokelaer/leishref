"""Tests for AGP derivation: locating a child assembly's layout in its parent."""

from pathlib import Path

import pytest

from leishref.agp import apply_agp, build_agp, derive_agp, derive_placements, read_fasta, revcomp, split_blocks


def write_fasta(path, seqs):
    with open(path, "w") as f:
        for name, seq in seqs.items():
            f.write(f">{name}\n")
            for i in range(0, len(seq), 60):
                f.write(seq[i : i + 60] + "\n")


@pytest.fixture
def synthetic(tmp_path):
    """Parent with 3 contigs; child joins c1(+) and c3(-) into a chromosome, keeps c2 alone."""
    import random

    random.seed(1)
    gen = lambda n: "".join(random.choice("ACGT") for _ in range(n))
    c1, c2, c3 = gen(3000), gen(1500), gen(2200)

    parent = {"c1": c1, "c2": c2, "c3": c3}
    child = {"chr1": c1 + "N" * 100 + revcomp(c3), "unplaced1": c2}

    p = tmp_path / "parent.fa"
    c = tmp_path / "child.fa"
    write_fasta(p, parent)
    write_fasta(c, child)
    return p, c, parent, child


def test_revcomp_roundtrip():
    assert revcomp(revcomp("ACGTTNAC")) == "ACGTTNAC"
    assert revcomp("AACCGGTT") == "AACCGGTT"


def test_split_blocks_breaks_on_gaps():
    blocks = split_blocks({"s1": "AAAA" + "N" * 20 + "CCCC"}, min_gap=10)
    assert [b.seq for b in blocks] == ["AAAA", "CCCC"]
    assert [b.offset for b in blocks] == [0, 24]


def test_split_blocks_ignores_short_gaps():
    blocks = split_blocks({"s1": "AAAANNCCCC"}, min_gap=10)
    assert len(blocks) == 1


def test_derive_placements_finds_orientation(synthetic):
    p, c, parent, child = synthetic
    placements, unplaced = derive_placements(read_fasta(p), read_fasta(c))

    assert unplaced == []
    by_parent = {x.parent_id: x for x in placements}
    assert by_parent["c1"].orientation == "+"
    assert by_parent["c3"].orientation == "-"
    assert by_parent["c1"].child_id == "chr1"
    assert by_parent["c2"].child_id == "unplaced1"


def test_derive_placements_reports_absent_sequence(tmp_path):
    import random

    random.seed(2)
    gen = lambda n: "".join(random.choice("ACGT") for _ in range(n))
    p, c = tmp_path / "p.fa", tmp_path / "c.fa"
    shared = gen(2000)
    write_fasta(p, {"kept": shared, "dropped": gen(2000)})
    write_fasta(c, {"chr1": shared})

    placements, unplaced = derive_placements(read_fasta(p), read_fasta(c))
    assert [x.parent_id for x in placements] == ["kept"]
    assert [b.parent_id for b in unplaced] == ["dropped"]


def test_agp_roundtrip_reconstructs_child(synthetic):
    """The point of the model: child FASTA is regenerable from parent + AGP."""
    p, c, parent, child = synthetic
    lines, stats = derive_agp(p, c)

    rebuilt = apply_agp(read_fasta(p), lines)
    assert rebuilt == child
    assert stats["coverage_of_non_n_parent"] == 100.0


def test_apply_agp_rejects_missing_component():
    lines = ["chr1\t1\t10\t1\tW\tghost\t1\t10\t+"]
    with pytest.raises(KeyError, match="ghost"):
        apply_agp({"real": "ACGT"}, lines)


def test_build_agp_emits_gap_records(synthetic):
    p, c, parent, child = synthetic
    placements, _ = derive_placements(read_fasta(p), read_fasta(c))
    lines = build_agp(placements, read_fasta(c))

    gaps = [line for line in lines if "\tN\t" in line]
    assert len(gaps) == 1
    assert gaps[0].split("\t")[5] == "100"
