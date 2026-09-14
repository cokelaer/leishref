"""Per-genome metadata: one directory, one metadata.yaml.

The shipped catalog lives at ``leishref/data/<id>/metadata.yaml``, where ``<id>`` is the
accession when there is one. A local database mirrors that shape at ``data/<alias>/``,
named by whatever alias the user chose, so the directory name *is* the alias and nothing
has to be kept in sync with a separate index.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import yaml

METADATA_FILE = "metadata.yaml"

#: Shipped catalog, updated by hand or by pull request.
CATALOG_DIR = Path(__file__).parent / "data"

#: Local database, relative to wherever leishref is run.
LOCAL_DIR = Path("data")


def today_iso() -> str:
    return datetime.now().isoformat()[:10]


@dataclass
class Genome:
    """One genome's metadata, as stored in its metadata.yaml."""

    identifier: str = ""
    source: Optional[str] = None
    accession: Optional[str] = None
    taxon_id: Optional[int] = None
    species: Optional[str] = None
    strain: Optional[str] = None
    assembly_name: Optional[str] = None
    release_version: Optional[str] = None
    files: dict = field(default_factory=dict)
    checksums: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    scaffold: dict = field(default_factory=dict)
    date_added: Optional[str] = None
    notes: Optional[str] = None

    #: Set when loaded; not written back.
    path: Optional[Path] = None

    @property
    def fasta(self) -> Optional[str]:
        return self.files.get("fasta")

    @property
    def gff(self) -> Optional[str]:
        return self.files.get("gff")

    @property
    def zenodo_doi(self) -> Optional[str]:
        return self.provenance.get("zenodo_doi")

    def file_paths(self) -> list[tuple[str, Path, Optional[str]]]:
        """(kind, path, recorded_md5) for each file that belongs to this genome."""
        if self.path is None:
            return []
        out = []
        for kind in ("fasta", "gff"):
            name = self.files.get(kind)
            if name:
                out.append((kind, self.path / name, self.checksums.get(kind)))
        return out

    def to_dict(self) -> dict:
        """YAML-bound fields, dropping empties so the file stays readable."""
        data = {
            "identifier": self.identifier,
            "source": self.source,
            "accession": self.accession,
            "taxon_id": self.taxon_id,
            "species": self.species,
            "strain": self.strain,
            "assembly_name": self.assembly_name,
            "release_version": self.release_version,
            "files": self.files,
            "checksums": self.checksums,
            "stats": self.stats,
            "provenance": self.provenance,
            "scaffold": self.scaffold,
            "date_added": self.date_added,
            "notes": self.notes,
        }
        return {k: v for k, v in data.items() if v not in (None, {}, "")}

    @classmethod
    def from_dict(cls, data: dict, path: Optional[Path] = None) -> "Genome":
        known = {f for f in cls.__dataclass_fields__ if f != "path"}
        return cls(path=path, **{k: v for k, v in (data or {}).items() if k in known})


def read_genome(directory: Path) -> Genome:
    """Load one genome directory."""
    directory = Path(directory)
    with open(directory / METADATA_FILE) as fh:
        data = yaml.safe_load(fh)
    genome = Genome.from_dict(data, path=directory)
    if not genome.identifier:
        genome.identifier = directory.name
    return genome


def write_genome(directory: Path, genome: Genome) -> Path:
    """Write metadata.yaml into a genome directory, creating it if needed."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / METADATA_FILE
    with open(target, "w") as fh:
        yaml.safe_dump(genome.to_dict(), fh, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return target


def iter_genomes(root: Path) -> Iterator[Genome]:
    """Every genome directory under root, in name order."""
    root = Path(root)
    if not root.is_dir():
        return
    for directory in sorted(root.iterdir()):
        if (directory / METADATA_FILE).is_file():
            yield read_genome(directory)


def catalog(root: Optional[Path] = None) -> list[Genome]:
    return list(iter_genomes(root or CATALOG_DIR))


def local(root: Optional[Path] = None) -> list[Genome]:
    return list(iter_genomes(root or LOCAL_DIR))


def find(genomes: list[Genome], key: str) -> Optional[Genome]:
    """Match on directory name, accession, or fasta filename."""
    for genome in genomes:
        if key in (genome.identifier, genome.accession, genome.fasta):
            return genome
    return None
