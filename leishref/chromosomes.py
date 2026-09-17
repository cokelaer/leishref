"""Chromosome name mapping and sequence renaming utilities."""

import re
from pathlib import Path
from typing import Optional

import yaml


def load_chromosome_map(data_dir: Path = None) -> dict:
    """Load chromosome name mapping from local database.

    Returns: {accession: [{"name": "chr I", "index": 1}, ...]}
    """
    if data_dir is None:
        from leishref.metadata import CATALOG_DIR

        data_dir = CATALOG_DIR

    map_file = data_dir / "chromosome_map.yaml"
    if not map_file.exists():
        return {}

    with open(map_file) as f:
        return yaml.safe_load(f) or {}


def save_chromosome_map(mapping: dict, data_dir: Path = None):
    """Save chromosome name mapping to local database."""
    if data_dir is None:
        from leishref.metadata import CATALOG_DIR

        data_dir = CATALOG_DIR

    map_file = data_dir / "chromosome_map.yaml"
    map_file.parent.mkdir(parents=True, exist_ok=True)

    with open(map_file, "w") as f:
        yaml.dump(mapping, f, default_flow_style=False, sort_keys=True)


def get_chromosome_info(accession: str, data_dir: Path = None) -> list[dict]:
    """Get chromosome info for accession from local database.

    Returns: [{"name": "chromosome I", "index": 1}, ...]
    """
    chrom_map = load_chromosome_map(data_dir)
    return chrom_map.get(accession, [])


def detect_sequences_from_fasta(fasta_path: Path) -> list[dict]:
    """Extract sequence headers from FASTA file.

    Returns: [{"accession": "NC_007067.7", "name": "NC_007067.7"}, ...]
    """
    sequences = []
    content = fasta_path.read_text()

    for match in re.finditer(r"^>(\S+)", content, re.MULTILINE):
        seq_id = match.group(1)
        index = len(sequences) + 1
        entry = {
            "accession": seq_id,
            "name": seq_id,
            "index": index,
        }
        # Mark sequence 37 as maxicircle (kinetoplast DNA)
        if index == 37:
            entry["type"] = "maxicircle"
        sequences.append(entry)

    return sequences


def rename_fasta_sequences(
    fasta_path: Path,
    accession: str,
    flavor: str = "chr",
    data_dir: Path = None,
) -> tuple[str, dict, Optional[str]]:
    """Rename sequences in FASTA using local chromosome database.

    Flavors:
    - 'chr': chromosome I, chromosome II, ...
    - 'name': use stored names from database
    - 'number': 1, 2, 3, ... (numeric index)
    - 'roman': I, II, III, ... (Roman numerals)

    Returns: (renamed FASTA content, mapping dict {old_name: new_name}, error message or None)
    """
    chrom_info = get_chromosome_info(accession, data_dir)

    if not chrom_info:
        # Auto-detect from FASTA and populate map
        chrom_info = detect_sequences_from_fasta(fasta_path)
        if not chrom_info:
            return fasta_path.read_text(), {}, f"No sequences found in {fasta_path.name}"

        # Save to chromosome map for future use
        chrom_map = load_chromosome_map(data_dir)
        chrom_map[accession] = chrom_info
        save_chromosome_map(chrom_map, data_dir)

    # Build mapping of sequence order to new names
    name_map = {}
    for i, info in enumerate(chrom_info, 1):
        old_name = info.get("accession", f"sequence_{i}")

        # Contigs (NW_*) keep original ID, no renaming
        if old_name.startswith("NW_"):
            new_name = old_name
        # Special handling for maxicircle (kinetoplast DNA)
        elif info.get("type") == "maxicircle":
            new_name = "maxicircle"
        elif flavor == "chr":
            new_name = f"chromosome {_roman_numeral(i)}"
        elif flavor == "name":
            new_name = info.get("name", old_name)
        elif flavor == "number":
            new_name = str(i)
        elif flavor == "roman":
            new_name = _roman_numeral(i)
        else:
            new_name = old_name

        name_map[old_name] = new_name

    content = fasta_path.read_text()

    for old, new in name_map.items():
        content = re.sub(
            rf"^>{re.escape(old)}(?:\s.*)?$",
            f">{new}",
            content,
            flags=re.MULTILINE,
        )

    return content, name_map, None


def _roman_numeral(n: int) -> str:
    """Convert number to Roman numeral."""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ""
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syms[i]
            n -= val[i]
        i += 1
    return roman_num
