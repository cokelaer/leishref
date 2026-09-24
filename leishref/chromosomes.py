"""Chromosome name mapping and sequence renaming utilities."""

import csv
import re
from pathlib import Path
from typing import Optional


def load_chromosome_map(data_dir: Path = None) -> dict:
    """Load chromosome mapping from CSV.

    Returns: {accession: {"chromosome": "1", "taxid": "", "origin": "GCA_..."}}
    """
    if data_dir is None:
        from leishref.metadata import CATALOG_DIR

        data_dir = CATALOG_DIR

    map_file = data_dir / "chromosome_map.csv"
    if not map_file.exists():
        return {}

    mapping = {}
    with open(map_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row and row.get("accession"):
                mapping[row["accession"]] = {
                    "chromosome": row.get("chromosome", ""),
                    "taxid": row.get("taxid", ""),
                    "origin": row.get("origin", ""),
                }
    return mapping


def get_chromosome_info(accession: str, data_dir: Path = None) -> Optional[dict]:
    """Get chromosome info for a sequence accession.

    Returns: {"chromosome": "1", "taxid": "", "origin": "GCA_..."} or None
    """
    chrom_map = load_chromosome_map(data_dir)
    return chrom_map.get(accession)


def get_genome_sequences(genome_accession: str, data_dir: Path = None) -> list[dict]:
    """Get all chromosome sequences for a genome accession.

    Returns: [{"accession": "CP022616.1", "chromosome": "1", ...}, ...]
    """
    if data_dir is None:
        from leishref.metadata import CATALOG_DIR

        data_dir = CATALOG_DIR

    map_file = data_dir / "chromosome_map.csv"
    if not map_file.exists():
        return []

    sequences = []
    with open(map_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row and row.get("origin") == genome_accession:
                sequences.append(row)
    return sequences


def detect_sequences_from_fasta(fasta_path: Path) -> list[str]:
    """Extract sequence IDs from FASTA file in order.

    Returns: ["NC_007067.7", "NC_007068.7", ...]
    """
    sequences = []
    content = fasta_path.read_text()

    for match in re.finditer(r"^>(\S+)", content, re.MULTILINE):
        sequences.append(match.group(1))

    return sequences


def extract_sequences_with_headers(fasta_path: Path) -> list[dict]:
    """Extract sequence ID and full header from FASTA file.

    Returns: [{"accession": "CM024314.1", "header": "CM024314.1 Leishmania tropica strain CDC216-162 chromosome 28, ..."}, ...]
    """
    sequences = []
    content = fasta_path.read_text()

    for match in re.finditer(r"^>([^\s]+)\s*(.*?)$", content, re.MULTILINE):
        accession = match.group(1)
        description = match.group(2) or ""
        sequences.append({"accession": accession, "header": f"{accession} {description}".strip()})

    return sequences


def get_taxid_from_species(species: str, data_dir: Path = None) -> Optional[int]:
    """Look up NCBI taxon ID for a species from mapping file.

    Args:
        species: Species name (e.g., "Leishmania donovani")
        data_dir: Catalog directory (default: CATALOG_DIR)

    Returns: NCBI taxon ID or None if not found
    """
    if data_dir is None:
        from leishref.metadata import CATALOG_DIR

        data_dir = CATALOG_DIR

    mapping_file = data_dir / "species_taxon_mapping.yaml"
    if not mapping_file.exists():
        return None

    import yaml

    try:
        with open(mapping_file) as f:
            data = yaml.safe_load(f) or {}
            if species in data:
                return data[species].get("primary")
    except Exception:
        pass

    return None


def parse_chromosome_from_header(header: str) -> Optional[str]:
    """Try to extract chromosome number from sequence header.

    Looks for patterns like "chromosome 28" or "chr28".
    Returns chromosome number or None if not found.
    """
    # Match "chromosome 28" or "chromosome28"
    match = re.search(r"chromosome\s*(\d+)", header, re.IGNORECASE)
    if match:
        return match.group(1)

    # Match "chr28" or "chr 28"
    match = re.search(r"chr\s*(\d+)", header, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def rename_fasta_sequences(
    fasta_path: Path,
    accession: str,
    flavor: str = "number",
    data_dir: Path = None,
    taxon_id: Optional[int] = None,
) -> tuple[str, dict, Optional[str]]:
    """Rename sequences in FASTA using local chromosome database.

    Flavors:
    - 'number': 1, 2, 3, ... (numeric index based on sequence order in file)
    - 'kraken': number|kraken:taxid|<TAXON_ID> format for Kraken classification

    Args:
        taxon_id: NCBI taxon ID (required for 'kraken' flavor)

    Returns: (renamed FASTA content, mapping dict {old_name: new_name}, error message or None)
    """
    sequences = detect_sequences_from_fasta(fasta_path)
    if not sequences:
        return fasta_path.read_text(), {}, f"No sequences found in {fasta_path.name}"

    # Build mapping of sequence order to new names
    name_map = {}
    for i, seq_id in enumerate(sequences, 1):
        # Contigs (NW_*) keep original ID, no renaming
        if seq_id.startswith("NW_"):
            new_name = seq_id
        elif flavor == "number":
            new_name = str(i)
        elif flavor == "kraken":
            if not taxon_id:
                return fasta_path.read_text(), {}, "Kraken flavor requires --taxid parameter"
            new_name = f"{i}|kraken:taxid|{taxon_id}"
        else:
            new_name = seq_id

        name_map[seq_id] = new_name

    content = fasta_path.read_text()

    for old, new in name_map.items():
        content = re.sub(
            rf"^>{re.escape(old)}(?:[ \t].*)?$",
            f">{new}",
            content,
            flags=re.MULTILINE,
        )

    return content, name_map, None
