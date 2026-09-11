"""Derive an AGP describing how a child assembly was laid out from a parent assembly.

Many "different" genomes are the same INSDC sequence re-oriented and joined into
chromosomes (TriTrypDB and ragtag both do this). Storing the AGP instead of the
child FASTA keeps provenance exact and avoids redistributing third-party sequence.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def revcomp(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def read_fasta(path: Path) -> dict[str, str]:
    """Read fasta into {id: uppercase_sequence}. Id is first whitespace/pipe-delimited token."""
    seqs: dict[str, str] = {}
    name = None
    buf: list[str] = []
    with open(path, "r") as f:
        for line in f:
            if line.startswith(">"):
                if name is not None:
                    seqs[name] = "".join(buf)
                name = re.split(r"[\s|]", line[1:].strip())[0]
                buf = []
            else:
                buf.append(line.strip().upper())
    if name is not None:
        seqs[name] = "".join(buf)
    return seqs


@dataclass
class Placement:
    parent_id: str
    parent_beg: int  # 1-based inclusive, within parent sequence
    parent_end: int  # 1-based inclusive
    child_id: str
    start: int  # 0-based inclusive, within child sequence
    end: int  # 0-based exclusive
    orientation: str  # "+" or "-"


@dataclass
class Block:
    """A gapless run of sequence within a parent record."""

    parent_id: str
    offset: int  # 0-based start within parent
    seq: str


def split_blocks(seqs: dict[str, str], min_gap: int = 10) -> list[Block]:
    """Decompose records into gapless blocks. Parent scaffolds may be split by the child,
    so contigs -- not whole scaffolds -- are the placeable unit."""
    blocks: list[Block] = []
    splitter = re.compile(r"[Nn]{%d,}" % min_gap)
    for name, seq in seqs.items():
        cursor = 0
        for m in splitter.finditer(seq):
            if m.start() > cursor:
                blocks.append(Block(name, cursor, seq[cursor : m.start()]))
            cursor = m.end()
        if cursor < len(seq):
            blocks.append(Block(name, cursor, seq[cursor:]))
    return blocks


def _probe(seq: str, probe_len: int, from_end: bool) -> Optional[tuple[str, int]]:
    """First N-free window of probe_len, scanned from start or end. Returns (window, offset)."""
    n = len(seq)
    if n < probe_len:
        return None
    positions = range(n - probe_len, -1, -1) if from_end else range(0, n - probe_len + 1)
    for off in positions:
        window = seq[off : off + probe_len]
        if "N" not in window:
            return window, off
    return None


class _Blob:
    """Concatenated child sequences with offset index, for single-pass substring search."""

    def __init__(self, seqs: dict[str, str]):
        self.names: list[str] = []
        self.starts: list[int] = []
        parts = []
        cursor = 0
        for name, seq in seqs.items():
            self.names.append(name)
            self.starts.append(cursor)
            parts.append(seq)
            cursor += len(seq)
        self.text = "".join(parts)

    def locate(self, pos: int) -> tuple[str, int]:
        """Map global blob offset to (sequence_id, local_offset)."""
        i = bisect_right(self.starts, pos) - 1
        return self.names[i], pos - self.starts[i]


def _verify(child_seq: str, expected: str, start: int, sample: int = 200) -> bool:
    """Confirm a candidate placement by spot-checking sequence identity, ignoring N."""
    if start < 0 or start + len(expected) > len(child_seq):
        return False
    step = max(1, len(expected) // sample)
    for i in range(0, len(expected), step):
        a, b = expected[i], child_seq[start + i]
        if a == "N" or b == "N":
            continue
        if a != b:
            return False
    return True


def _scan(blob: _Blob, child: dict[str, str], needle: str, expect: str, off: int, hint: int, max_candidates: int):
    """Find `needle` in the blob and return the verified (child_id, start) for `expect`.

    Searches from `hint` first: consecutive blocks of one parent scaffold almost always
    land adjacently in the child, so the hint turns a full 30Mb scan into a local one.
    """
    spans = [(hint, len(blob.text)), (0, hint)] if hint else [(0, len(blob.text))]
    for lo, hi in spans:
        pos = blob.text.find(needle, lo, hi)
        tries = 0
        while pos != -1 and tries < max_candidates:
            cid, local = blob.locate(pos)
            cand = local - off
            if _verify(child[cid], expect, cand):
                return cid, cand, pos
            pos = blob.text.find(needle, pos + 1, hi)
            tries += 1
    return None


def _place_block(
    block: Block,
    blob: _Blob,
    child: dict[str, str],
    probe_len: int,
    max_candidates: int,
    hint: dict,
) -> Optional[Placement]:
    """Locate one gapless block in the child, forward or reverse-complemented."""
    head = _probe(block.seq, probe_len, from_end=False)
    if head is None:
        return None
    window, off = head
    span = len(block.seq)
    beg, end = block.offset + 1, block.offset + span

    last_pos, last_orient = hint.get(block.parent_id, (0, "+"))

    fwd = (window, block.seq, off, "+")
    rev = (revcomp(window), revcomp(block.seq), span - off - probe_len, "-")
    order = [rev, fwd] if last_orient == "-" else [fwd, rev]

    for needle, expect, needle_off, orient in order:
        hit = _scan(blob, child, needle, expect, needle_off, last_pos, max_candidates)
        if hit:
            cid, cand, pos = hit
            hint[block.parent_id] = (max(0, pos - 1000), orient)
            return Placement(block.parent_id, beg, end, cid, cand, cand + span, orient)

    return None


def derive_placements(
    parent: dict[str, str],
    child: dict[str, str],
    probe_len: int = 60,
    min_gap: int = 10,
    max_candidates: int = 50,
) -> tuple[list[Placement], list[Block]]:
    """Locate each gapless parent block inside the child. Returns (placements, unplaced_blocks)."""
    blob = _Blob(child)
    blocks = split_blocks(parent, min_gap)
    placements: list[Placement] = []
    unplaced: list[Block] = []
    hint: dict[str, tuple[int, str]] = {}

    for block in blocks:
        hit = _place_block(block, blob, child, probe_len, max_candidates, hint)
        if hit is None:
            unplaced.append(block)
        else:
            placements.append(hit)

    return placements, unplaced


def build_agp(placements: list[Placement], child: dict[str, str], gap_type: str = "scaffold") -> list[str]:
    """Render placements as AGP 2.0 lines, inserting N gaps between placed components."""
    by_child: dict[str, list[Placement]] = {}
    for p in placements:
        by_child.setdefault(p.child_id, []).append(p)

    lines = ["##agp-version 2.0"]
    for cid in child:
        parts = sorted(by_child.get(cid, []), key=lambda p: p.start)
        if not parts:
            continue
        part_num = 0
        cursor = 0
        for p in parts:
            if p.start > cursor:
                part_num += 1
                lines.append(
                    f"{cid}\t{cursor + 1}\t{p.start}\t{part_num}\tN\t{p.start - cursor}\t{gap_type}\tyes\talign_genus"
                )
            part_num += 1
            lines.append(
                f"{cid}\t{p.start + 1}\t{p.end}\t{part_num}\tW\t{p.parent_id}\t{p.parent_beg}\t{p.parent_end}\t{p.orientation}"
            )
            cursor = max(cursor, p.end)
        tail = len(child[cid])
        if cursor < tail:
            part_num += 1
            lines.append(f"{cid}\t{cursor + 1}\t{tail}\t{part_num}\tN\t{tail - cursor}\t{gap_type}\tyes\talign_genus")
    return lines


def derive_agp(parent_fasta: Path, child_fasta: Path, probe_len: int = 60, min_gap: int = 10) -> tuple[list[str], dict]:
    """Derive AGP mapping child layout back to parent sequences. Returns (agp_lines, stats)."""
    parent = read_fasta(parent_fasta)
    child = read_fasta(child_fasta)

    placements, unplaced = derive_placements(parent, child, probe_len, min_gap)
    lines = build_agp(placements, child)

    placed_bases = sum(p.end - p.start for p in placements)
    unplaced_bases = sum(len(b.seq) for b in unplaced)
    parent_bases = sum(len(s) for s in parent.values())
    non_n_parent = parent_bases - sum(s.count("N") for s in parent.values())
    forward = sum(1 for p in placements if p.orientation == "+")
    split_parents = {p.parent_id for p in placements}

    stats = {
        "parent_sequences": len(parent),
        "child_sequences": len(child),
        "blocks_total": len(placements) + len(unplaced),
        "blocks_placed": len(placements),
        "blocks_unplaced": len(unplaced),
        "unplaced_bases": unplaced_bases,
        "forward": forward,
        "reverse": len(placements) - forward,
        "parent_bases": parent_bases,
        "child_bases": sum(len(s) for s in child.values()),
        "placed_bases": placed_bases,
        "coverage_of_non_n_parent": round(100.0 * placed_bases / non_n_parent, 3) if non_n_parent else 0.0,
        "parent_sequences_placed": len(split_parents),
        "child_sequences_used": len({p.child_id for p in placements}),
        "largest_unplaced": sorted((len(b.seq), b.parent_id) for b in unplaced)[-5:][::-1],
    }
    return lines, stats


def write_agp(path: Path, lines: list[str]) -> None:
    Path(path).write_text("\n".join(lines) + "\n")


def apply_agp(parent: dict[str, str], agp_lines: list[str]) -> dict[str, str]:
    """Rebuild child sequences from parent sequences plus an AGP.

    Closes the loop on storing layout instead of sequence: the child FASTA never has
    to be redistributed, because it can be regenerated from its source assembly.
    """
    out: dict[str, list[str]] = {}
    for line in agp_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) < 9:
            continue
        obj, comp_type = f[0], f[4]
        parts = out.setdefault(obj, [])
        if comp_type == "N" or comp_type == "U":
            parts.append("N" * int(f[5]))
        else:
            comp_id, beg, end, orient = f[5], int(f[6]), int(f[7]), f[8]
            if comp_id not in parent:
                raise KeyError(f"AGP references {comp_id}, absent from parent assembly")
            piece = parent[comp_id][beg - 1 : end]
            parts.append(revcomp(piece) if orient == "-" else piece)
    return {k: "".join(v) for k, v in out.items()}


def read_agp(path: Path) -> list[str]:
    return Path(path).read_text().splitlines()
