"""NCBI genome download via datasets CLI."""

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from leishdb.checksums import md5_file, sequence_length


class NCBIError(Exception):
    pass


def fetch_fasta_gff(accession: str, outdir: Path) -> tuple[Optional[Path], Optional[Path]]:
    """Download fasta+gff from NCBI via datasets CLI. Returns (fasta_path, gff_path) or (None, None)."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        try:
            cmd = [
                "datasets",
                "download",
                "genome",
                "accession",
                accession,
                "--include",
                "genome,gff3",
                "--filename",
                str(tmpdir / "dataset.zip"),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                if "not found" in result.stderr or "error" in result.stderr.lower():
                    return None, None
                raise NCBIError(f"datasets download failed: {result.stderr}")

            zippath = tmpdir / "dataset.zip"
            if not zippath.exists():
                return None, None

            with zipfile.ZipFile(zippath, "r") as z:
                z.extractall(tmpdir)

            fasta_file = None
            gff_file = None

            for f in tmpdir.rglob("*.fna"):
                fasta_file = f
                break
            for f in tmpdir.rglob("*.gff"):
                gff_file = f
                break

            if fasta_file:
                new_fasta = outdir / fasta_file.name
                new_fasta.write_bytes(fasta_file.read_bytes())
                fasta_file = new_fasta

            if gff_file:
                new_gff = outdir / gff_file.name
                new_gff.write_bytes(gff_file.read_bytes())
                gff_file = new_gff

            return fasta_file, gff_file

        except subprocess.CalledProcessError as e:
            raise NCBIError(f"datasets command failed: {e}")


def fetch_metadata(accession: str) -> dict:
    """Fetch assembly metadata from NCBI (sequencing tech, bioproject, biosample, raw reads)."""
    try:
        cmd = ["datasets", "summary", "genome", "accession", accession, "--as-json-lines"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            if "assemblies" in data:
                for asm in data["assemblies"]:
                    info = {}
                    if "assembly_info" in asm:
                        ai = asm["assembly_info"]
                        info["assembly_name"] = ai.get("assembly_name")
                    if "paired_ends" in asm:
                        info["sequencing_technology"] = "paired-end"
                    if "bioproject_accn" in asm:
                        info["bioproject"] = asm.get("bioproject_accn")
                    if "biosample_accn" in asm:
                        info["biosample"] = asm.get("biosample_accn")
                    return info
        return {}
    except Exception:
        return {}
