"""Ragtag scaffolding and AGP-based contig pruning."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Set


class RagtagError(Exception):
    pass


def find_ragtag_bin() -> str:
    """Find ragtag.py in PATH or known conda envs."""
    import os
    import shutil

    if shutil.which("ragtag.py"):
        return "ragtag.py"
    if shutil.which("ragtag"):
        return "ragtag"

    known_path = Path.home() / "miniconda3/envs/py311/bin/ragtag.py"
    if known_path.exists():
        return str(known_path)

    raise RagtagError("ragtag.py not found in PATH or conda envs")


def run_scaffold(reference_fasta: Path, query_fasta: Path, outdir: Path) -> tuple[Path, Path]:
    """Run ragtag.py scaffold. Return (fasta, agp) paths."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ragtag_bin = find_ragtag_bin()
    tmpdir = Path(tempfile.mkdtemp())

    try:
        cmd = [ragtag_bin, "scaffold", str(reference_fasta), str(query_fasta), "-o", str(tmpdir)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RagtagError(f"ragtag scaffold failed: {result.stderr}")

        scaffold_fasta = tmpdir / "ragtag.scaffold.fasta"
        scaffold_agp = tmpdir / "ragtag.scaffold.agp"

        if not scaffold_fasta.exists() or not scaffold_agp.exists():
            raise RagtagError("ragtag did not produce output files")

        out_fasta = outdir / "ragtag.scaffold.fasta"
        out_agp = outdir / "ragtag.scaffold.agp"
        out_fasta.write_bytes(scaffold_fasta.read_bytes())
        out_agp.write_bytes(scaffold_agp.read_bytes())

        return out_fasta, out_agp

    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


def parse_agp(agp_file: Path) -> dict[str, list[tuple[int, int, str]]]:
    """Parse AGP file. Returns {contig_name: [(start, end, ref_chromosome)]}.

    AGP columns: object, object_beg, object_end, part_number, component_type, component_id, ...
    For 'D' (DNA), component_id is the contig name; for 'N' (gap), we skip.
    """
    placements = {}
    with open(agp_file, "r") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.strip().split("\t")
            if len(fields) < 5:
                continue
            obj_id = fields[0]  # scaffold/chromosome name
            comp_type = fields[4]  # D or N
            if comp_type == "D":
                comp_id = fields[5]  # contig name
                obj_beg = int(fields[1])
                obj_end = int(fields[2])
                if comp_id not in placements:
                    placements[comp_id] = []
                placements[comp_id].append((obj_beg, obj_end, obj_id))
    return placements


def clean_scaffolded_fasta(fasta_file: Path, agp_file: Path, keep_patterns: Optional[list[str]] = None) -> str:
    """Filter fasta to keep only contigs anchored to reference chromosomes + whitelisted contigs.

    Args:
        fasta_file: input fasta from ragtag.scaffold.fasta
        agp_file: ragtag.scaffold.agp
        keep_patterns: contig name patterns to always keep (e.g., ['maxicircle', 'kinetoplast'])

    Returns:
        cleaned fasta content as string
    """
    if keep_patterns is None:
        keep_patterns = ["maxicircle", "kinetoplast", "kDNA"]

    placements = parse_agp(agp_file)
    keep_contigs = set()

    for contig_name in placements:
        keep_contigs.add(contig_name)

    for pattern in keep_patterns:
        with open(fasta_file, "r") as f:
            for line in f:
                if line.startswith(">") and pattern.lower() in line.lower():
                    contig_name = line.split()[0][1:]
                    keep_contigs.add(contig_name)

    result = []
    current_contig = None
    with open(fasta_file, "r") as f:
        for line in f:
            if line.startswith(">"):
                current_contig = line.split()[0][1:]
                if current_contig in keep_contigs:
                    result.append(line)
            elif current_contig in keep_contigs:
                result.append(line)

    return "".join(result)
