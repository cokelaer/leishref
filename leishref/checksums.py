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


def genome_stats(fpath: Path) -> dict:
    """Size, contig count, GC, contig N50, ambiguous bases and gap count, in one pass.

    A gap is a run of N of any length, so the count reflects how many joins or unknown
    stretches a sequence contains rather than how many bases they span.
    """
    lengths = []
    current = 0
    gc = 0
    acgt = 0
    n_bases = 0
    gaps = 0
    in_gap = False

    with open(fpath, "r") as handle:
        for line in handle:
            if line.startswith(">"):
                if current:
                    lengths.append(current)
                current = 0
                in_gap = False
                continue
            seq = line.strip().upper()
            if not seq:
                continue
            current += len(seq)
            gc += seq.count("G") + seq.count("C")
            n_here = seq.count("N")
            n_bases += n_here
            acgt += len(seq) - n_here
            if n_here:
                for char in seq:
                    if char == "N":
                        if not in_gap:
                            gaps += 1
                            in_gap = True
                    else:
                        in_gap = False
            else:
                in_gap = False

    if current:
        lengths.append(current)

    total = sum(lengths)
    n50 = 0
    if total:
        running = 0
        for length in sorted(lengths, reverse=True):
            running += length
            if running >= total / 2:
                n50 = length
                break

    return {
        "num_bases": total,
        "num_contigs": len(lengths),
        "gc_percent": round(gc / acgt * 100, 2) if acgt else 0.0,
        "contig_n50": n50,
        "num_ambiguous": n_bases,
        "num_gaps": gaps,
    }
