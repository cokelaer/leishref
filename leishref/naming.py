"""Suggest an alias for a genome.

The alias a user picks is theirs, but starting from a blank prompt is unhelpful, so
leishref proposes `<Lspec>.<source>.<discriminator>`: enough to tell two genomes of the
same species apart at a glance.
"""

import re
from typing import Optional

#: NCBI assigns these when a submitter supplies no assembly name. They carry no
#: information beyond the accession, so the accession is preferred.
OPAQUE_ASSEMBLY = re.compile(r"^ASM\d+v\d+$", re.IGNORECASE)

SOURCE_TAGS = {
    "NCBI": "ncbi",
    "TriTrypDB": "tritryp",
    "Zenodo": "zenodo",
    "Local": "local",
    "Scaffold": "scaf",
}


def species_abbrev(species: Optional[str]) -> str:
    """'Leishmania tropica' -> 'Ltrop'. Four letters keeps close neighbours apart."""
    if not species:
        return "Unk"
    parts = species.replace("_", " ").split()
    # "Leishmania sp. Ghana": the marker carries no information, so abbreviate what
    # follows it, or every unplaced isolate in the genus becomes "Lsp.".
    if len(parts) > 2 and parts[1].lower() in ("sp.", "cf.", "aff.", "nr."):
        return parts[0][0].upper() + parts[2][:4].lower()
    if len(parts) >= 2:
        return parts[0][0].upper() + parts[1][:4].lower()
    return parts[0][0].upper() + parts[0][1:5].lower()


def source_tag(source: Optional[str], release: Optional[str] = None) -> str:
    """A TriTrypDB release changes the annotation, so it is folded in."""
    tag = SOURCE_TAGS.get(source or "", (source or "unk").lower())
    if tag == "tritryp" and release:
        tag = f"tritryp{release}"
    return tag


def _clean(value: str) -> str:
    """NCBI ships values such as 'MHOM_LB _2017_IK', a space next to an underscore."""
    return re.sub(r"[\s_]+", "_", value.strip()).strip("_")


def strain_from_assembly_name(assembly_name: Optional[str], species: Optional[str]) -> Optional[str]:
    """Recover a strain NCBI recorded in assembly_name because strain was empty."""
    if not assembly_name or OPAQUE_ASSEMBLY.match(assembly_name.strip()):
        return None
    name = _clean(assembly_name)
    if species:
        prefix = _clean(species).lower()
        if name.lower().startswith(prefix):
            name = name[len(prefix) :].strip("_-")
    name = re.sub(r"[-_]\d+(\.\d+)+$", "", name)
    return name or None


def _from_identifier(identifier: str) -> Optional[str]:
    """Local assemblies record the assembler only in their name; keep what differs."""
    tokens = [t for t in identifier.split(".") if t]
    tail = tokens[tokens.index("scaffold") + 1 :] if "scaffold" in tokens else tokens[1:]
    return "_".join(tail) or None


def discriminator(genome) -> str:
    """What tells this genome apart from others of the same species and source."""
    if genome.source in ("Zenodo", "Local", "Scaffold"):
        from_name = _from_identifier(genome.identifier or "")
        if from_name:
            return from_name

    if genome.strain and genome.strain.strip():
        return _clean(genome.strain)

    rescued = strain_from_assembly_name(genome.assembly_name, genome.species)
    if rescued:
        return rescued

    return (genome.accession or _clean(genome.identifier or "unknown")).strip()


def suggest_alias(genome) -> str:
    """A readable name for this genome, for the user to accept or ignore."""
    if genome.source == "Leishref scaffold" and genome.identifier:
        return genome.identifier

    # For scaffolds, format as <query_abbrev>.scaffold.<reference>
    if genome.source == "Scaffold" and genome.identifier and "scaffold" in genome.identifier:
        parts = genome.identifier.split(".")
        if len(parts) >= 3 and "scaffold" in parts:
            idx = parts.index("scaffold")
            if idx >= 1:
                query = parts[0]  # e.g., "Ltropica"
                reference = parts[idx - 1]  # e.g., "Ld1S"
                return f"{species_abbrev(query)}.scaffold.{reference}"

    return ".".join(
        (
            species_abbrev(genome.species),
            source_tag(genome.source, genome.release_version),
            discriminator(genome),
        )
    )
