"""Alias-named symlinks created beside wherever leishref was run."""

import os
from pathlib import Path

import pytest

from leishref.links import LinkConflict, link_name, link_paths, make_link


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "NCBI").mkdir()
    fasta = tmp_path / "NCBI" / "GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna"
    gff = tmp_path / "NCBI" / "GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.gff"
    fasta.write_text(">c1\nACGT\n")
    gff.write_text("##gff-version 3\n")
    return tmp_path, fasta, gff


def test_link_name_standardizes_fasta_extension():
    assert link_name("Ltrop.ncbi.L590", Path("x/y.fna")) == "Ltrop.ncbi.L590.fna"
    assert link_name("Ltrop.ncbi.L590", Path("x/y.fasta")) == "Ltrop.ncbi.L590.fna"
    assert link_name("Ltrop.ncbi.L590", Path("x/y.fa")) == "Ltrop.ncbi.L590.fna"


def test_link_is_relative_so_the_tree_stays_movable(tree):
    base, fasta, _ = tree
    link = make_link("Ltrop.ncbi.L590", fasta, base)

    target = os.readlink(link)
    assert not os.path.isabs(target)
    assert target == "NCBI/GCA_000410715.1_Leishmania_tropica_L590-2.0.2_genomic.fna"
    assert link.read_text() == ">c1\nACGT\n"


def test_repeated_linking_is_a_no_op(tree):
    base, fasta, _ = tree
    assert make_link("Ltrop.ncbi.L590", fasta, base) is not None
    assert make_link("Ltrop.ncbi.L590", fasta, base) is None


def test_stale_symlink_is_repointed(tree):
    base, fasta, _ = tree
    (base / "NCBI" / "other.fna").write_text(">z\nTTTT\n")
    make_link("Ltrop.ncbi.L590", base / "NCBI" / "other.fna", base)

    link = make_link("Ltrop.ncbi.L590", fasta, base)
    assert os.readlink(link).endswith("L590-2.0.2_genomic.fna")


def test_regular_file_is_never_clobbered(tree):
    base, fasta, _ = tree
    victim = base / "Ltrop.ncbi.L590.fna"
    victim.write_text("someone's real data")

    with pytest.raises(LinkConflict):
        make_link("Ltrop.ncbi.L590", fasta, base)
    assert victim.read_text() == "someone's real data"


def test_link_paths_covers_every_file_given(tree):
    base, fasta, gff = tree
    made = link_paths("Ltrop.ncbi.L590", [fasta, gff], base)
    assert {p.name for p in made} == {"Ltrop.ncbi.L590.fna", "Ltrop.ncbi.L590.gff"}


def test_link_paths_ignores_none(tree):
    base, fasta, _ = tree
    made = link_paths("Ltrop.ncbi.L590", [fasta, None], base)
    assert [p.name for p in made] == ["Ltrop.ncbi.L590.fna"]
