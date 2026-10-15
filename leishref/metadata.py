"""Per-genome metadata: one directory, one metadata.yaml.

The shipped catalog lives at ``leishref/data/<group>/<id>/metadata.yaml`` (TriTrypDB
entries one level deeper, by release: ``tritrypdb/71/<id>``). The shared cache under
``~/.config/leishref`` mirrors that layout, with each genome stored under its cache key
(see cache_key()) rather than under any project's alias.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import yaml

METADATA_FILE = "metadata.yaml"

#: Shipped catalog, updated by hand or by pull request.
CATALOG_DIR = Path(__file__).parent / "data"

#: Catalog entries are grouped by where the genome came from, one directory per origin.
CATALOG_GROUPS = ("ncbi", "ncbi_nucleotide", "scaffolds", "zenodo", "tritrypdb", "custom", "local")

#: Global cache directory for downloaded genomes, shared across all projects.
CACHE_DIR = Path.home() / ".config" / "leishref"

#: Local database, defaults to global cache (can be overridden with --local-dir).
LOCAL_DIR = CACHE_DIR


def today_iso() -> str:
    return datetime.now().isoformat()[:10]


GLOB_CHARS = "*?["


def is_glob(term: str) -> bool:
    """True when a search term is meant to be matched as a wildcard pattern."""
    return any(char in term for char in GLOB_CHARS)


def _term_matches(term: str, haystack: str) -> bool:
    """Substring match, or a glob match when the term carries wildcards.

    The pattern is padded with ``*`` on both sides so that a wildcard term matches
    anywhere in the record, exactly as a plain term does.
    """
    if is_glob(term):
        return fnmatch.fnmatch(haystack, f"*{term}*")
    return term in haystack


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
    assembly_level: Optional[str] = None
    #: What kind of sequence this entry is, when it isn't a nuclear assembly - e.g.
    #: "kinetoplast" or "kinetoplast,maxicircle". Unset for ordinary nuclear genomes.
    #: NCBI's own assembly_level doesn't distinguish this (a lone maxicircle still
    #: comes back as "Chromosome"), so nothing infers it automatically; set it
    #: explicitly with --molecule-type on fetch-genome/fetch-nucleotide/add.
    molecule_type: Optional[str] = None
    release_date: Optional[str] = None
    release_version: Optional[str] = None
    #: Set on a TriTrypDB entry superseded by the same strain in a later release.
    superseded_by: Optional[str] = None
    files: dict = field(default_factory=dict)
    checksums: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    #: TriTrypDB specifics (release number, source URL, download date).
    tritrypdb: dict = field(default_factory=dict)
    license: dict = field(default_factory=dict)
    access: dict = field(default_factory=dict)
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

    def haystack(self) -> str:
        """Everything worth matching a search term against, lowercased.

        Includes provenance identifiers so a bioproject or DOI finds its genome, and
        the filenames so a name copied off disk does too.
        """
        parts = [
            self.identifier,
            self.source,
            self.accession,
            str(self.taxon_id) if self.taxon_id else None,
            self.species,
            self.strain,
            self.assembly_name,
            self.molecule_type,
            self.release_version,
            self.notes,
            *self.files.values(),
            *(str(v) for v in self.provenance.values()),
            *(str(v) for v in self.scaffold.values()),
        ]
        return " ".join(p for p in parts if p).lower()

    def matches(self, terms) -> bool:
        """True when every term appears somewhere in this genome's metadata.

        A term containing a shell wildcard (``*``, ``?`` or ``[...]``) is matched as a
        glob rather than as a substring, so ``GCA_0002*`` and ``L*tropica`` work and a
        bare ``*`` matches every genome. Plain terms keep their substring behaviour.
        """
        haystack = self.haystack()
        return all(_term_matches(term.lower(), haystack) for term in terms)

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
            "assembly_level": self.assembly_level,
            "molecule_type": self.molecule_type,
            "release_date": self.release_date,
            "release_version": self.release_version,
            "superseded_by": self.superseded_by,
            "files": self.files,
            "checksums": self.checksums,
            "stats": self.stats,
            "provenance": self.provenance,
            "tritrypdb": self.tritrypdb,
            "license": self.license,
            "access": self.access,
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


def catalog_group(genome) -> str:
    """The catalog subdirectory a genome belongs in.

    Grouping follows the source: custom entries stay in custom/ (even if on Zenodo),
    scaffolds go to scaffolds/, NCBI assemblies to ncbi/, standalone NCBI nuccore
    records (not a GCA/GCF assembly - e.g. a lone kinetoplast/maxicircle sequence)
    to ncbi_nucleotide/, TriTrypDB to tritrypdb/, and Zenodo-published genomes to
    zenodo/.
    """
    source = (genome.source or "").lower()
    if source == "custom":
        return "custom"
    if genome.scaffold:
        return "scaffolds"
    if source == "ncbi-nucleotide":
        return "ncbi_nucleotide"
    if source in ("tritrypdb", "ncbi"):
        return source
    accession = genome.accession or ""
    if accession.startswith(("GCA_", "GCF_")):
        return "ncbi"
    if source == "zenodo" or genome.zenodo_doi:
        return "zenodo"
    return "local"


def tritrypdb_release(genome) -> Optional[str]:
    """The TriTrypDB release number of an entry, from its metadata or else its identifier."""
    release = (genome.tritrypdb or {}).get("release")
    if release is not None:
        return str(release)
    match = re.match(r"TriTrypDB-(\d+)_", genome.identifier or "")
    return match.group(1) if match else None


def catalog_subdir(genome) -> Path:
    """The directory, relative to a catalog or cache root, that holds this genome's own
    directory: its group, plus the release for TriTrypDB (``tritrypdb/71``)."""
    group = catalog_group(genome)
    if group == "tritrypdb":
        release = tritrypdb_release(genome)
        if release:
            return Path(group) / release
    return Path(group)


def cache_key(genome) -> str:
    """The shared cache's own name for this genome: its accession, or its catalog
    identifier when there isn't one (scaffolds, local/custom entries, TriTrypDB).

    Never a user-chosen alias. The cache is shared across every project on the
    machine, so it's keyed by what a genome *is*, not by what any one project calls
    it - two aliases (or two projects) for the same accession share one download
    instead of duplicating it, and an alias can never collide with a different
    genome's cached copy.
    """
    return genome.accession or genome.identifier


def catalog_entry_dir(root: Path, genome) -> Path:
    """Where this genome's metadata.yaml belongs under a catalog root."""
    return Path(root) / catalog_subdir(genome) / genome.identifier


def cache_dir(root: Path, genome) -> Path:
    """Where this genome is cached under a local-database root: the catalog's own
    layout (``ncbi/``, ``tritrypdb/71/``, ...) with the genome stored under its cache key."""
    return Path(root) / catalog_subdir(genome) / cache_key(genome)


def iter_genomes(root: Path) -> Iterator[Genome]:
    """Every genome directory under root, in name order.

    Entries sit one level down (``ncbi/GCA_*``), two for TriTrypDB (``tritrypdb/71/*``),
    or directly under the root in a cache that predates the grouped layout, so the tree
    is walked down to the first directory holding a metadata.yaml.
    """
    root = Path(root)
    if not root.is_dir():
        return
    stack = [(root, 0)]
    while stack:
        directory, depth = stack.pop(0)
        for entry in sorted(directory.iterdir()):
            if (entry / METADATA_FILE).is_file():
                yield read_genome(entry)
            elif entry.is_dir() and depth < 2:
                stack.append((entry, depth + 1))


def catalog(root: Optional[Path] = None) -> list[Genome]:
    return list(iter_genomes(root or CATALOG_DIR))


def local(root: Optional[Path] = None) -> list[Genome]:
    return list(iter_genomes(root or LOCAL_DIR))


_ALIASES_CACHE = None


def load_aliases(root: Optional[Path] = None) -> dict[str, str]:
    """Load common aliases from aliases.txt (accession -> alias mapping)."""
    global _ALIASES_CACHE
    if _ALIASES_CACHE is not None:
        return _ALIASES_CACHE

    aliases = {}
    aliases_file = (root or CATALOG_DIR) / "aliases.txt"
    if aliases_file.exists():
        with open(aliases_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) == 2:
                    accession, alias = parts
                    aliases[alias] = accession
    _ALIASES_CACHE = aliases
    return aliases


def find(genomes: list[Genome], key: str, catalog_root: Optional[Path] = None) -> Optional[Genome]:
    """Match on directory name, accession, alias, or fasta filename."""
    for genome in genomes:
        if key in (genome.identifier, genome.accession, genome.fasta):
            return genome
    # Check aliases
    aliases = load_aliases(catalog_root)
    if key in aliases:
        alias_target = aliases[key]
        for genome in genomes:
            if alias_target in (genome.accession, genome.identifier):
                return genome
    return None


def get_catalog_alias(accession: str, catalog_root: Optional[Path] = None) -> Optional[str]:
    """Get the catalog alias for an accession, if one exists."""
    aliases = load_aliases(catalog_root)
    for alias, acc in aliases.items():
        if acc == accession:
            return alias
    return None
