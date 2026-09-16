"""Prune scaffolds to keep only mapped sequences and kinetoplast."""

from pathlib import Path
from typing import Set


def get_kinetoplast_patterns() -> Set[str]:
    """Return patterns matching kinetoplast sequences."""
    return {
        "kinetoplast",
        "maxicircle",
        "maxi",
        "mitochondrion",
        "mitochondrial",
        "mtdna",
        "mt_dna",
    }


def is_kinetoplast(seq_name: str) -> bool:
    """Check if sequence is kinetoplast-related."""
    patterns = get_kinetoplast_patterns()
    name_lower = seq_name.lower()
    return any(p in name_lower for p in patterns)


def prune_fasta(fasta_path: Path, mapped_names: Set[str]) -> str:
    """Keep only mapped sequences + kinetoplast. Return pruned FASTA."""
    lines = []
    current_seq = None
    keep_seq = False

    with open(fasta_path) as f:
        for line in f:
            if line.startswith(">"):
                # New sequence header
                header = line[1:].split()[0]  # Get first token after '>'
                keep_seq = header in mapped_names or is_kinetoplast(header)
                current_seq = header
                if keep_seq:
                    lines.append(line)
            elif keep_seq:
                lines.append(line)

    return "".join(lines)
