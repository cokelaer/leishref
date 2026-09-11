"""Manifest CSV handling: provenance tracking for all genomes in the database."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIRS = ["NCBI", "TriTryDB68", "MyAssemblies", "Scaffold"]


def resolve_path(filename: str, basedir: Path = Path(".")) -> Optional[Path]:
    """Locate a manifest filename on disk. Manifest stores bare names; data lives in DATA_DIRS."""
    if not filename:
        return None
    basedir = Path(basedir)
    direct = basedir / filename
    if direct.exists():
        return direct
    for d in DATA_DIRS:
        cand = basedir / d / filename
        if cand.exists():
            return cand
    for d in DATA_DIRS:
        root = basedir / d
        if root.is_dir():
            for hit in root.rglob(filename):
                return hit
    return None


MANIFEST_COLUMNS = [
    "filename",
    "gff_filename",
    "source",
    "accession",
    "assembly_name",
    "release_version",
    "species",
    "strain",
    "alias",
    "md5sum_fasta",
    "md5sum_gff",
    "scaffold_reference_alias",
    "scaffold_tool_version",
    "cleaned",
    "cleaned_from",
    "derived_from",
    "agp_filename",
    "zenodo_doi",
    "sequencing_technology",
    "bioproject",
    "biosample",
    "raw_reads_accession",
    "num_bases",
    "num_contigs",
    "gc_percent",
    "date_added",
    "notes",
]


class ManifestRow(dict):
    """Single row in manifest. Subclass of dict for flexibility."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for col in MANIFEST_COLUMNS:
            if col not in self:
                self[col] = None


class Manifest:
    """Read/write/append manifest CSV."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> list[ManifestRow]:
        """Read all rows from manifest. Return empty list if file doesn't exist."""
        if not self.path.exists():
            return []
        rows = []
        with open(self.path, "r") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return []
            for row in reader:
                rows.append(ManifestRow(**row))
        return rows

    def write(self, rows: list[ManifestRow]) -> None:
        """Write all rows to manifest (overwrite)."""
        with open(self.path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col) for col in MANIFEST_COLUMNS})

    def append(self, row: ManifestRow) -> None:
        """Append a single row. Creates file if needed."""
        rows = self.read()
        rows.append(row)
        self.write(rows)

    def append_many(self, rows: list[ManifestRow]) -> None:
        """Append multiple rows."""
        existing = self.read()
        existing.extend(rows)
        self.write(existing)

    def replace_by_accession(self, accession: str, new_row: ManifestRow) -> None:
        """Replace row with matching accession, or append if not found."""
        rows = self.read()
        for i, row in enumerate(rows):
            if row.get("accession") == accession:
                rows[i] = new_row
                self.write(rows)
                return
        # Not found, append instead
        self.append(new_row)

    def find_by_filename(self, filename: str) -> Optional[ManifestRow]:
        """Find row by fasta filename."""
        for row in self.read():
            if row.get("filename") == filename:
                return row
        return None

    def find_by_accession(self, accession: str) -> Optional[ManifestRow]:
        """Find row by accession (for deduplication)."""
        for row in self.read():
            if row.get("accession") == accession:
                return row
        return None

    def find_by_alias(self, alias: str) -> Optional[ManifestRow]:
        """Find row by alias."""
        for row in self.read():
            if row.get("alias") == alias:
                return row
        return None

    def today_iso(self) -> str:
        """Today's date in ISO format."""
        return datetime.now().isoformat()[:10]
