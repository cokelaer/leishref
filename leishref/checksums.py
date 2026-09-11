"""Compute and verify MD5 checksums for fasta/gff files."""

import hashlib
import subprocess
from pathlib import Path


def md5_file(fpath: Path) -> str:
    """Compute MD5 checksum of a file."""
    fpath = Path(fpath)
    hash_md5 = hashlib.md5()
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def sequence_length(fpath: Path) -> int:
    """Total length of all sequences in fasta file (excluding headers, newlines)."""
    fpath = Path(fpath)
    length = 0
    with open(fpath, "r") as f:
        in_seq = False
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                in_seq = True
            elif in_seq and line:
                length += len(line)
    return length


def contig_count(fpath: Path) -> int:
    """Count contigs (headers) in fasta."""
    fpath = Path(fpath)
    count = 0
    with open(fpath, "r") as f:
        for line in f:
            if line.startswith(">"):
                count += 1
    return count


def gc_percent(fpath: Path) -> float:
    """Calculate GC content percentage."""
    fpath = Path(fpath)
    gc_count = 0
    total_bases = 0
    with open(fpath, "r") as f:
        for line in f:
            if not line.startswith(">"):
                seq = line.strip().upper()
                gc_count += seq.count("G") + seq.count("C")
                total_bases += len(seq)
    if total_bases == 0:
        return 0.0
    return round((gc_count / total_bases) * 100, 2)
