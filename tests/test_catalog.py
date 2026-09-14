"""The shipped catalog layered under a user's local manifest."""

from pathlib import Path

import pytest

from leishref.manifest import CATALOG_PATH, Catalog, Manifest, ManifestRow


@pytest.fixture
def catalog_file(tmp_path):
    path = tmp_path / "catalog.csv"
    Manifest(path).write(
        [
            ManifestRow(filename="a.fa", alias="A", accession="GCA_1", source="NCBI", md5sum_fasta="aaa"),
            ManifestRow(filename="b.fa", alias="B", accession="GCA_2", source="NCBI", md5sum_fasta="bbb"),
        ]
    )
    return path


def test_shipped_catalog_exists_and_is_populated():
    assert CATALOG_PATH.exists(), "catalog must ship inside the package"
    assert len(Manifest(CATALOG_PATH).read()) > 0


def test_reads_catalog_when_no_local(tmp_path, catalog_file):
    cat = Catalog(local=tmp_path / "absent.csv", catalog=catalog_file)
    assert {r["filename"] for r in cat.read()} == {"a.fa", "b.fa"}
    assert cat.counts() == (2, 0)
    assert all(r["_origin"] == "catalog" for r in cat.read())


def test_local_rows_are_added(tmp_path, catalog_file):
    local = tmp_path / "local.csv"
    Manifest(local).write([ManifestRow(filename="mine.fa", alias="M")])

    cat = Catalog(local=local, catalog=catalog_file)
    assert cat.counts() == (2, 1)
    assert cat.find_by_alias("M")["_origin"] == "local"


def test_local_row_overrides_catalog_row(tmp_path, catalog_file):
    local = tmp_path / "local.csv"
    Manifest(local).write([ManifestRow(filename="a.fa", alias="A", md5sum_fasta="corrected")])

    cat = Catalog(local=local, catalog=catalog_file)
    rows = cat.read()
    assert len(rows) == 2, "override replaces rather than duplicates"
    assert cat.find_by_filename("a.fa")["md5sum_fasta"] == "corrected"
    assert cat.counts() == (1, 1)


def test_upsert_never_writes_to_catalog(tmp_path, catalog_file):
    before = catalog_file.read_text()
    cat = Catalog(local=tmp_path / "local.csv", catalog=catalog_file)
    cat.upsert_local(ManifestRow(filename="new.fa", alias="N"))

    assert catalog_file.read_text() == before
    assert (tmp_path / "local.csv").exists()
    assert cat.find_by_alias("N") is not None


def test_upsert_replaces_matching_filename(tmp_path, catalog_file):
    cat = Catalog(local=tmp_path / "local.csv", catalog=catalog_file)
    cat.upsert_local(ManifestRow(filename="x.fa", md5sum_fasta="one"))
    cat.upsert_local(ManifestRow(filename="x.fa", md5sum_fasta="two"))

    local_rows = Manifest(tmp_path / "local.csv").read()
    assert len(local_rows) == 1
    assert local_rows[0]["md5sum_fasta"] == "two"


def test_explicit_single_manifest_is_not_double_counted(catalog_file):
    """--manifest X means that file alone, not X overlaid on itself."""
    cat = Catalog(local=catalog_file, catalog=catalog_file)
    assert len(cat.read()) == 2


def test_resolve_prefers_alias_then_filename_then_accession(tmp_path, catalog_file):
    cat = Catalog(local=tmp_path / "absent.csv", catalog=catalog_file)
    assert cat.resolve("A")["filename"] == "a.fa"
    assert cat.resolve("b.fa")["alias"] == "B"
    assert cat.resolve("GCA_2")["filename"] == "b.fa"
    assert cat.resolve("nope") is None


def test_origin_is_transient_and_never_persisted(tmp_path, catalog_file):
    cat = Catalog(local=tmp_path / "local.csv", catalog=catalog_file)
    row = cat.read()[0]
    assert "_origin" in row
    cat.upsert_local(ManifestRow(**{k: v for k, v in row.items() if k != "_origin"}))
    assert "_origin" not in (tmp_path / "local.csv").read_text()
