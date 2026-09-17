"""Compute and verify MD5 checksums for fasta/gff files."""

import hashlib
import re
from pathlib import Path


def md5_file(fpath: Path) -> str:
    """Compute MD5 checksum of a file."""
    fpath = Path(fpath)
    hash_md5 = hashlib.md5()
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _n50_l50(lengths: list) -> tuple:
    """(N50, L50): the length at which cumulative sorted length passes half, and how
    many sequences that took."""
    total = sum(lengths)
    if not total:
        return 0, 0
    running = 0
    for count, length in enumerate(sorted(lengths, reverse=True), start=1):
        running += length
        if running >= total / 2:
            return length, count
    return 0, 0


def _iter_scaffolds(fpath: Path):
    """Yield each record's sequence, uppercased."""
    buf: list = []
    started = False
    with open(fpath, "r") as handle:
        for line in handle:
            if line.startswith(">"):
                if started:
                    yield "".join(buf)
                buf = []
                started = True
            else:
                buf.append(line.strip().upper())
    if started:
        yield "".join(buf)


def genome_stats(fpath: Path, min_gap: int = 10) -> dict:
    """Assembly statistics at both scaffold and contig level.

    A FASTA record is a scaffold; the gapless blocks inside it are contigs. Reporting
    only the record count conflates the two, which for a chromosome-level assembly is
    the difference between 36 and a few thousand.

    ``min_gap`` is the shortest run of N that breaks a scaffold in two. Shorter runs are
    ambiguous bases inside a contig rather than gaps, which is the rule NCBI applies:
    with min_gap=10 these figures reproduce NCBI's assembly_stats exactly.
    """
    gap = re.compile(r"N{%d,}" % min_gap)

    scaffolds: list = []
    contigs: list = []
    gc = acgt = ambiguous = gap_bases = gaps = 0

    for seq in _iter_scaffolds(fpath):
        if not seq:
            continue
        scaffolds.append(len(seq))
        gc += seq.count("G") + seq.count("C")
        n_here = seq.count("N")
        ambiguous += n_here
        acgt += len(seq) - n_here

        cursor = 0
        for match in gap.finditer(seq):
            gaps += 1
            gap_bases += match.end() - match.start()
            if match.start() > cursor:
                contigs.append(match.start() - cursor)
            cursor = match.end()
        if cursor < len(seq):
            contigs.append(len(seq) - cursor)

    scaffold_n50, scaffold_l50 = _n50_l50(scaffolds)
    contig_n50, contig_l50 = _n50_l50(contigs)
    total = sum(scaffolds)

    return {
        "num_bases": total,
        "num_ungapped": total - gap_bases,
        "num_scaffolds": len(scaffolds),
        "num_contigs": len(contigs),
        "gc_percent": round(gc / acgt * 100, 2) if acgt else 0.0,
        "scaffold_n50": scaffold_n50,
        "scaffold_l50": scaffold_l50,
        "contig_n50": contig_n50,
        "contig_l50": contig_l50,
        "num_ambiguous": ambiguous,
        "num_gaps": gaps,
    }
