"""Generate stable, readable aliases of the form <Lspec>.<source>.<discriminator>.

Aliases are lookup keys, not parsed structure: the discriminator may itself contain
dots (an accession) without changing how anything resolves them.
"""

import re
from typing import Iterable, Optional

#: NCBI assigns these when a submitter supplies no assembly name. They carry no
#: information beyond the accession, so the accession is used instead.
OPAQUE_ASSEMBLY = re.compile(r"^ASM\d+v\d+$", re.IGNORECASE)

SOURCE_TAGS = {
    "NCBI": "ncbi",
    "TriTrypDB": "tritryp",
    "MyAssembly": "mine",
    "Scaffold": "scaf",
}


def species_abbrev(species: Optional[str]) -> str:
    """'Leishmania tropica' -> 'Ltrop'. Genus initial plus four letters of the epithet."""
    if not species:
        return "Unk"
    parts = species.replace("_", " ").split()
    if len(parts) >= 2:
        return parts[0][0].upper() + parts[1][:4].lower()
    # Already-compressed forms such as 'LtropicaCDC'
    token = parts[0]
    return token[0].upper() + token[1:5].lower()


def source_tag(source: Optional[str], release: Optional[str] = None) -> str:
    """Source, with the release folded in where a release changes the annotation.

    A Zenodo DOI is not a source: it records where an assembly was published, not
    where it came from, so it never appears here.
    """
    tag = SOURCE_TAGS.get(source or "", (source or "unk").lower())
    if tag == "tritryp" and release:
        tag = f"tritryp{release}"
    return tag


def _clean(value: str) -> str:
    """Normalise a name into an alias component.

    NCBI ships values such as 'MHOM_LB _2017_IK', where the stray space sits next to an
    underscore, so separator runs are collapsed rather than merely substituted.
    """
    return re.sub(r"[\s_]+", "_", value.strip()).strip("_")


def strain_from_assembly_name(assembly_name: Optional[str], species: Optional[str]) -> Optional[str]:
    """Recover a strain that NCBI recorded in assembly_name because strain was empty."""
    if not assembly_name or OPAQUE_ASSEMBLY.match(assembly_name.strip()):
        return None
    name = _clean(assembly_name)
    if species:
        prefix = _clean(species).lower()
        if name.lower().startswith(prefix):
            name = name[len(prefix) :].strip("_-")
    # Trailing assembly version, e.g. 'L590-2.0.2'
    name = re.sub(r"[-_]\d+(\.\d+)+$", "", name)
    return name or None


def _discriminator_from_filename(filename: str) -> Optional[str]:
    """For local assemblies the only distinguishing detail is in the filename.

    'Ltropica.Ld1S.scaffold.pecat.filtered.fasta' -> 'pecat_filtered': the tokens after
    'scaffold' are what actually differ between these files.
    """
    stem = re.sub(r"\.(fa|fna|fasta)$", "", filename, flags=re.IGNORECASE)
    tokens = [t for t in stem.split(".") if t]
    if "scaffold" in tokens:
        tail = tokens[tokens.index("scaffold") + 1 :]
    else:
        tail = tokens[1:]
    return "_".join(tail) or None


def discriminator(row: dict) -> str:
    """What distinguishes this genome inside its species and source."""
    source = row.get("source")
    if source in ("MyAssembly", "Scaffold"):
        from_name = _discriminator_from_filename(row.get("filename") or "")
        if from_name:
            return from_name

    strain = row.get("strain")
    if strain and strain.strip():
        return _clean(strain)

    rescued = strain_from_assembly_name(row.get("assembly_name"), row.get("species"))
    if rescued:
        return rescued

    accession = row.get("accession")
    if accession:
        return accession.strip()

    return _clean(row.get("filename") or "unknown")


def make_alias(row: dict) -> str:
    """Full alias for one row, before collisions are resolved."""
    return ".".join(
        (
            species_abbrev(row.get("species")),
            source_tag(row.get("source"), row.get("release_version")),
            discriminator(row),
        )
    )


def unique_alias(row: dict, taken: set) -> str:
    """Alias for a row that does not clash with `taken`, falling back to the accession."""
    alias = make_alias(row)
    if alias not in taken:
        return alias
    accession = row.get("accession")
    candidate = f"{alias}.{accession}" if accession else alias
    n = 2
    while candidate in taken:
        candidate = f"{alias}.{n}"
        n += 1
    return candidate


def assign_aliases(rows: Iterable[dict], overwrite: bool = False) -> dict[str, str]:
    """Work out an alias per row, keeping existing ones unless overwrite is set.

    Returns {filename: alias}. Collisions fall back to the accession, then to a
    numeric suffix, so the result is always unique within the catalog.
    """
    rows = list(rows)
    taken = set()
    if not overwrite:
        taken = {r["alias"] for r in rows if r.get("alias")}

    assigned: dict[str, str] = {}
    for row in rows:
        filename = row.get("filename")
        if not filename:
            continue
        if not overwrite and row.get("alias"):
            assigned[filename] = row["alias"]
            continue

        alias = unique_alias(row, taken)
        taken.add(alias)
        assigned[filename] = alias
    return assigned
