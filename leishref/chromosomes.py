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


def rename_fasta_sequences(
    fasta_path: Path,
    accession: str,
    flavor: str = "chr",
    data_dir: Path = None,
) -> str:
    """Rename sequences in FASTA using local chromosome database, or by order.

    Flavors:
    - 'chr': chromosome I, chromosome II, ...
    - 'name': use stored names from database (requires chromosome info)
    - 'number': 1, 2, 3, ... (numeric index)
    - 'roman': I, II, III, ... (Roman numerals)

    If no chromosome info exists, flavors 'chr', 'number', 'roman' rename by sequence order.
    The 'name' flavor requires chromosome database info and returns original if not found.

    Returns: renamed FASTA content as string
    """
    chrom_info = get_chromosome_info(accession, data_dir)

    content = fasta_path.read_text()
    name_map = {}

    if chrom_info:
        # Use chromosome database if available
        for i, info in enumerate(chrom_info, 1):
            old_name = info.get("accession", f"sequence_{i}")

            if flavor == "chr":
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
    else:
        # No chromosome info: rename by sequence order from FASTA file
        if flavor == "name":
            # Can't do 'name' flavor without chromosome database
            return content

        # Count sequences in file and rename by order
        seq_index = 0
        for line in content.split("\n"):
            if line.startswith(">"):
                seq_index += 1
                header = line[1:].split()[0]  # Get accession (first word after '>')

                if flavor == "chr":
                    new_name = f"chromosome {_roman_numeral(seq_index)}"
                elif flavor == "number":
                    new_name = str(seq_index)
                elif flavor == "roman":
                    new_name = _roman_numeral(seq_index)
                else:
                    new_name = header

                name_map[header] = new_name

    # Apply name mappings
    for old, new in name_map.items():
        content = re.sub(
            rf"^>({re.escape(old)})(?:\s|$)",
            f">{new} ",
            content,
            flags=re.MULTILINE,
        )

    return content


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
