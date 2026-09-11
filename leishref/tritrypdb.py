"""TriTrypDB release-68 genome download."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from leishref.checksums import md5_file, sequence_length

TRITRYPDB_BASE = "https://tritrypdb.org/common/downloads/release-68"


class TriTrypDBError(Exception):
    pass


def download_fasta_gff(species_strain: str, outdir: Path) -> tuple[Optional[Path], Optional[Path]]:
    """Download fasta+gff from TriTrypDB release 68. Species_strain like 'Leishmania_major_Friedlin'."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    fasta_url = f"{TRITRYPDB_BASE}/fasta/genome/{species_strain}_Genome.fasta"
    gff_url = f"{TRITRYPDB_BASE}/gff/genome/{species_strain}.gff"

    fasta_file = None
    gff_file = None

    try:
        fasta_file = outdir / f"{species_strain}_Genome.fasta"
        result = subprocess.run(
            ["curl", "-f", "-o", str(fasta_file), fasta_url],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not fasta_file.exists():
            fasta_file = None

        gff_file = outdir / f"{species_strain}.gff"
        result = subprocess.run(
            ["curl", "-f", "-o", str(gff_file), gff_url], capture_output=True, text=True, check=False
        )
        if result.returncode != 0 or not gff_file.exists():
            gff_file = None

        return fasta_file, gff_file

    except Exception as e:
        raise TriTrypDBError(f"TriTrypDB download failed: {e}")
