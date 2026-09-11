"""Test manifest CSV reading/writing."""

import tempfile
from pathlib import Path

import pytest

from leishref.manifest import Manifest, ManifestRow


def test_manifest_create_and_append():
    """Create manifest and append row."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.csv"
        manifest = Manifest(manifest_path)

        row = ManifestRow(
            filename="Ld1S.fa",
            source="NCBI",
            accession="GCA_000410715.1",
            species="Leishmania",
            strain="donovani",
            md5sum_fasta="abc123",
            date_added="2026-09-11",
        )

        manifest.append(row)
        rows = manifest.read()

        assert len(rows) == 1
        assert rows[0]["filename"] == "Ld1S.fa"
        assert rows[0]["accession"] == "GCA_000410715.1"


def test_manifest_find_by_filename():
    """Find row by filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.csv"
        manifest = Manifest(manifest_path)

        manifest.append(ManifestRow(filename="Ld1S.fa", source="NCBI"))
        manifest.append(ManifestRow(filename="Ltropica.L590.fa", source="NCBI"))

        row = manifest.find_by_filename("Ltropica.L590.fa")
        assert row is not None
        assert row["filename"] == "Ltropica.L590.fa"


def test_manifest_find_by_accession():
    """Find row by accession."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.csv"
        manifest = Manifest(manifest_path)

        manifest.append(ManifestRow(filename="Ld1S.fa", accession="GCA_000410715.1"))
        row = manifest.find_by_accession("GCA_000410715.1")
        assert row is not None
        assert row["accession"] == "GCA_000410715.1"


def test_manifest_append_many():
    """Append multiple rows at once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.csv"
        manifest = Manifest(manifest_path)

        rows = [
            ManifestRow(filename="Ld1S.fa", source="NCBI"),
            ManifestRow(filename="Ltropica.L590.fa", source="NCBI"),
        ]
        manifest.append_many(rows)

        all_rows = manifest.read()
        assert len(all_rows) == 2
