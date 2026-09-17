"""Consistency of the hand-maintained aliases.txt."""

import re
from collections import Counter

import pytest

from leishref.metadata import CATALOG_DIR, load_aliases

ALIASES_FILE = CATALOG_DIR / "aliases.txt"
NCBI_DIR = CATALOG_DIR / "ncbi"


@pytest.fixture(scope="module")
def pairs():
    rows = []
    for line in ALIASES_FILE.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        assert len(parts) == 2, f"expected accession<TAB>alias, got: {line!r}"
        rows.append((parts[0], parts[1]))
    assert rows
    return rows


def test_aliases_are_unique(pairs):
    dups = [a for a, n in Counter(alias for _, alias in pairs).items() if n > 1]
    assert not dups, f"duplicate aliases: {dups}"


def test_accessions_are_unique(pairs):
    dups = [a for a, n in Counter(acc for acc, _ in pairs).items() if n > 1]
    assert not dups, f"duplicate accessions: {dups}"


def test_aliases_match_ncbi_catalog(pairs):
    # Only check NCBI accessions (GCA_/GCF_), exclude scaffolds and custom genomes
    ncbi_in_file = {acc for acc, _ in pairs if acc.startswith(("GCA_", "GCF_"))}
    in_catalog = {d.name for d in NCBI_DIR.iterdir() if (d / "metadata.yaml").is_file()}
    assert in_catalog - ncbi_in_file == set(), "catalog entries without alias"
    assert ncbi_in_file - in_catalog == set(), "aliases without catalog entry"


def test_alias_format(pairs):
    for _, alias in pairs:
        assert re.fullmatch(r"L[a-z]{1,2}[A-Za-z0-9_.-]*", alias), alias
        assert not re.search(r"_ASM\d+|_v\d+$|\(|annotation", alias), alias


def test_gca_twin_of_gcf_carries_gca_suffix(pairs):
    by_acc = dict(pairs)
    for acc, alias in pairs:
        if acc.startswith("GCF_"):
            twin = "GCA_" + acc[4:]
            if twin in by_acc:
                assert by_acc[twin] == alias + "_GCA", (acc, alias, by_acc[twin])


def test_load_aliases_reads_every_row(pairs):
    loaded = load_aliases()
    assert len(loaded) == len(pairs)
