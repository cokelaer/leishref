"""Standalone NCBI nucleotide (nuccore) record download via bioservices EUtils.

Unlike an assembly (GCA_/GCF_, fetched with `datasets` in ncbi.py), a nuccore record
is a single sequence - e.g. a lone kinetoplast/maxicircle deposited without an
accompanying nuclear genome assembly. It has no scaffold/contig structure and no
`datasets` support, so it needs its own fetch path through NCBI's EUtils.
"""

from pathlib import Path
from typing import Optional


class NuccoreError(Exception):
    pass


def _client(email: Optional[str] = None):
    from bioservices import EUtils

    return EUtils(email=email) if email else EUtils()


def fetch_nucleotide_fasta(accession: str, outdir: Path, email: Optional[str] = None) -> Path:
    """Download one nuccore record as FASTA. Raises NuccoreError if NCBI has nothing."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    client = _client(email)
    try:
        fasta = client.EFetch("nuccore", accession, retmode="text", rettype="fasta")
    except Exception as exc:
        raise NuccoreError(f"EFetch failed for {accession}: {exc}") from exc

    if not fasta:
        raise NuccoreError(f"NCBI nuccore has no data for {accession}")

    if isinstance(fasta, bytes):
        fasta = fasta.decode()
    if not fasta.startswith(">"):
        raise NuccoreError(f"Unexpected EFetch response for {accession}: {fasta[:200]!r}")

    target = outdir / f"{accession}.fasta"
    target.write_text(fasta)
    return target


def fetch_nucleotide_metadata(accession: str, email: Optional[str] = None) -> dict:
    """Organism, strain, taxon id, title and dates for one nuccore record.

    Empty dict when NCBI has nothing for this accession.
    """
    client = _client(email)
    try:
        found = client.ESearch("nuccore", accession)
        uids = (found or {}).get("idlist") or []
        if not uids:
            return {}
        summary = client.ESummary("nuccore", uids[0])
    except Exception as exc:
        raise NuccoreError(f"ESearch/ESummary failed for {accession}: {exc}") from exc

    record = (summary or {}).get(uids[0]) or {}
    if not record:
        return {}

    return {
        "accession": record.get("accessionversion") or accession,
        "taxon_id": record.get("taxid"),
        "organism": record.get("organism"),
        "strain": record.get("strain") or record.get("subname"),
        "title": record.get("title"),
        "release_date": (record.get("createdate") or "").replace("/", "-") or None,
        "length": record.get("slen"),
    }
