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


def _parse_summary(data: dict) -> dict:
    """Pull the fields we keep out of one `datasets summary` record."""
    info = data.get("assembly_info", {})
    organism = data.get("organism", {})
    # NCBI records the strain under infraspecific_names, not in organism_name. Where a
    # submitter registered a WHO designation as an isolate, strain is empty instead.
    infraspecific = organism.get("infraspecific_names") or {}
    return {
        "accession": data.get("accession"),
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
        "stats": stats_from_summary(data.get("assembly_stats") or {}),
    }


def stats_from_summary(raw: dict) -> dict:
    """Map NCBI's assembly_stats onto our field names.

    These agree with computing the same figures from the FASTA. `gc_percent` is derived
    from NCBI's own counts rather than read from its `gc_percent` field, which is rounded
    to the nearest 0.5. `num_gaps` has no equivalent in the summary and is filled in when
    the sequence is fetched.
    """
    if not raw:
        return {}

    def num(key, cast=int):
        value = raw.get(key)
        if value in (None, ""):
            return None
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None

    total = num("total_sequence_length")
    ungapped = num("total_ungapped_length")
    atgc = num("atgc_count")
    gc_count = num("gc_count")

    stats = {
        "num_bases": total,
        "num_ungapped": ungapped,
        "num_scaffolds": num("number_of_scaffolds"),
        "num_contigs": num("number_of_contigs"),
        "gc_percent": round(gc_count / atgc * 100, 2) if gc_count and atgc else None,
        "scaffold_n50": num("scaffold_n50"),
        "scaffold_l50": num("scaffold_l50"),
        "contig_n50": num("contig_n50"),
        "contig_l50": num("contig_l50"),
        "num_ambiguous": total - atgc if total is not None and atgc is not None else None,
    }
    return {k: v for k, v in stats.items() if v is not None}


def _summary(accessions: list) -> list:
    """Run `datasets summary` for one batch of accessions."""
    cmd = ["datasets", "summary", "genome", "accession", *accessions, "--as-json-lines"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    out = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def fetch_metadata(accession: str) -> dict:
    """Metadata for one assembly. Empty dict when NCBI has nothing."""
    records = _summary([accession])
    return _parse_summary(records[0]) if records else {}


def fetch_metadata_many(accessions, batch_size: int = 50):
    """Metadata for many assemblies, batched. Yields (accession, metadata)."""
    accessions = list(accessions)
    for start in range(0, len(accessions), batch_size):
        batch = accessions[start : start + batch_size]
        records = _summary(batch)

        # One unrecognised accession makes `datasets` reject the whole batch, so fall
        # back to asking one at a time rather than losing the rest.
        if not records and len(batch) > 1:
            records = [r for accession in batch for r in _summary([accession])]

        found = {}
        for record in records:
            parsed = _parse_summary(record)
            if parsed.get("accession"):
                found[parsed["accession"]] = parsed
        for accession in batch:
            yield accession, found.get(accession, {})
