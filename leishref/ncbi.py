"""NCBI genome download via datasets CLI."""

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional


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
                # Use same prefix as FASTA for GFF naming consistency
                if fasta_file:
                    fasta_stem = fasta_file.stem  # e.g., "GCF_000002875.2_ASM287v2_genomic"
                    new_gff = outdir / f"{fasta_stem}.gff"
                else:
                    new_gff = outdir / gff_file.name
                new_gff.write_bytes(gff_file.read_bytes())
                gff_file = new_gff

            return fasta_file, gff_file

        except subprocess.CalledProcessError as e:
            raise NCBIError(f"datasets command failed: {e}")


def fetch_metadata(accession: str) -> dict:
    """Fetch assembly metadata from NCBI: taxonomy, assembly name, sequencing tech, project ids."""
    cmd = ["datasets", "summary", "genome", "accession", accession, "--as-json-lines"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {}

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        data = json.loads(line)
        info = data.get("assembly_info", {})
        organism = data.get("organism", {})
        # NCBI records the strain under infraspecific_names, not in organism_name.
        infraspecific = organism.get("infraspecific_names") or {}
        return {
            "taxon_id": organism.get("tax_id"),
            "organism_name": organism.get("organism_name"),
            "strain": infraspecific.get("strain") or infraspecific.get("isolate"),
            "assembly_name": info.get("assembly_name"),
            "assembly_level": info.get("assembly_level"),
            "release_date": info.get("release_date"),
            "assembler": info.get("assembly_method"),
            "sequencing_technology": info.get("sequencing_tech"),
            "bioproject": info.get("bioproject_accession"),
            "biosample": (info.get("biosample") or {}).get("accession"),
        }
    return {}
