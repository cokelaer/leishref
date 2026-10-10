"""Comparison table of every public *Leishmania* nuclear assembly.

One row per current NCBI assembly, built from the NCBI Datasets ``dataset_report`` for the genus
(taxon 5658). Most columns are NCBI's own fields; the rest (``platform``, ``lr``, ``assembler``,
``asm_mode``, ``ref_inherited``, ``contig_class``, ``exp_chr``, ``gapless``) are derived by the rules
below, plus the few per-accession judgement calls kept in ``data/assembly_curation.yaml``.

Why ``contig_class`` exists: a "contig" count only measures what the reads supported when the
assembly is de novo. A reference-guided assembly (reads mapped onto a reference, consensus called)
inherits the reference's contiguity, so its N50 says nothing about the data.
"""

import csv
import re
from pathlib import Path
from typing import Iterable, Optional

import requests
import yaml

from leishref.ncbi import species_from_organism

TAXON_LEISHMANIA = 5658
REPORT_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2alpha/genome/taxon/{taxon}/dataset_report"
CURATION_FILE = Path(__file__).parent / "data" / "assembly_curation.yaml"

COLUMNS = [
    "accession",
    "organism",
    "strain",
    "infraspecific",
    "level",
    "name",
    "date",
    "submitter",
    "seq_tech",
    "method",
    "total_len",
    "n_contigs",
    "contig_n50",
    "n_scaf",
    "scaf_n50",
    "gaps",
    "gc",
    "refseq_cat",
    "bioproject",
    "year",
    "platform",
    "lr",
    "exp_chr",
    "gapless",
    "assembler",
    "asm_mode",
    "ref_inherited",
    "contig_class",
]

#: Assembler recognised in NCBI's free-text ``assembly_method``, first match wins. Order matters:
#: "HGAP v. 2; Celera Assembler; CANU" is a Canu assembly and "Canu v. 1.7; SPAdes" too, so the
#: long-read assemblers come first. The mapping side of ``REFERENCE_GUIDED`` marks read-mappers
#: and reference-based pipelines, whose output follows the reference.
ASSEMBLERS = [
    (r"\bcanu\b", "Canu"),
    (r"\bhgap", "HGAP"),
    (r"\bflye", "Flye"),
    (r"\bnecat\b", "NECAT"),
    (r"\bmasurca\b", "MaSuRCA"),
    (r"\bngsep\b|\brgaat\b|\bsmalt\b|\bbwa\b|burrows?[- ]wheeler|\bbowtie\b", "reference-guided"),
    (r"\bnewbler\b|gs de novo", "Newbler / GS De Novo"),
    (r"\ballpaths", "ALLPATHS"),
    (r"\bmegahit\b", "MEGAHIT"),
    (r"\bspades\b", "SPAdes"),
    (r"soap ?denovo", "SOAPdenovo"),
    (r"\bvelvet\b", "Velvet"),
    (r"\babyss\b", "ABySS"),
    (r"\ba5\b|a5-miseq", "a5-miseq"),
    (r"\bclc\b", "CLC"),
    (r"\bgeneious\b", "Geneious"),
]
UNCLEAR_METHODS = (r"\bvarious\b", r"\bhybrid pipeline\b")

LONG_READ = re.compile(r"nanopore|minion|gridion|promethion|pacbio|\brs ?ii\b|sequel|hifi", re.I)
NANOPORE = re.compile(r"nanopore|minion|gridion|promethion", re.I)
PACBIO = re.compile(r"pacbio|\brs ?ii\b|sequel|hifi", re.I)
ILLUMINA = re.compile(r"illumina|hiseq|miseq|nextseq|novaseq|\bgaii", re.I)


def load_curation(path: Optional[Path] = None) -> dict:
    return yaml.safe_load(Path(path or CURATION_FILE).read_text())


def fetch_reports(taxon: int = TAXON_LEISHMANIA, timeout: int = 60) -> list:
    """Every assembly report for a taxon, all versions, following NCBI's paging."""
    reports, token = [], None
    while True:
        params = {"filters.assembly_version": "all_assemblies", "page_size": 1000}
        if token:
            params["page_token"] = token
        response = requests.get(REPORT_URL.format(taxon=taxon), params=params, timeout=timeout)
        response.raise_for_status()
        page = response.json()
        reports += page.get("reports", [])
        token = page.get("next_page_token")
        if not token:
            return reports


def platform_of(seq_tech) -> tuple[str, bool]:
    """(platform label, uses long reads) from the submitter's free-text sequencing technology."""
    tech = seq_tech or ""
    ont, pb, ill = bool(NANOPORE.search(tech)), bool(PACBIO.search(tech)), bool(ILLUMINA.search(tech))
    if ont and pb:
        label = "ONT+PacBio" + ("+Illumina" if ill else "")
    elif ont:
        label = "ONT+Illumina" if ill else "ONT only"
    elif pb:
        label = "PacBio+Illumina" if ill else "PacBio only"
    else:
        label = "Illumina only" if ill else "unspecified"
    return label, ont or pb


def assembler_of(method) -> tuple[str, str]:
    """(assembler, assembly mode) from NCBI's free-text assembly method."""
    if not method:
        return "unstated", "unstated"
    text = method.lower()
    for pattern, name in ASSEMBLERS:
        if re.search(pattern, text):
            return name, ("reference-guided" if name == "reference-guided" else "de novo")
    if any(re.search(p, text) for p in UNCLEAR_METHODS):
        return "other/unclear", "other/unclear"
    return "other/unclear", "other/unclear"


def expected_chromosomes(organism: str, curation: dict) -> int:
    """35 for the Viannia subgenus species (two chromosomes fused), 36 otherwise."""
    species = species_from_organism(organism).removeprefix("Leishmania ").strip()
    return 35 if species in curation["viannia_species"] else 36


def _infraspecific(report: dict) -> str:
    names = report.get("organism", {}).get("infraspecific_names") or {}
    return names.get("strain") or ""


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _curated(accession: str, report: dict, table: dict):
    """A curation entry for this accession, or for the GenBank assembly it mirrors (RefSeq)."""
    return table.get(accession) or table.get(report.get("paired_accession") or "")


def build_row(report: dict, curation: dict) -> dict:
    info = report.get("assembly_info", {})
    stats = report.get("assembly_stats", {})
    accession = report["accession"]
    platform, long_read = platform_of(info.get("sequencing_tech"))
    assembler, mode = assembler_of(info.get("assembly_method"))

    overrides = _curated(accession, report, curation["contig_class"]) or {}
    if mode == "reference-guided":
        contig_class = "reference-guided (declared)"
    else:
        contig_class = overrides.get("contig_class", "read-earned")
    ref_inherited = mode == "reference-guided" or bool(overrides.get("ref_inherited"))

    total = _int(stats.get("total_sequence_length"))
    ungapped = _int(stats.get("total_ungapped_length"))
    date = info.get("release_date") or ""
    organism = report.get("organism", {}).get("organism_name", "")
    return {
        "accession": accession,
        "organism": organism,
        "strain": "",
        "infraspecific": _infraspecific(report),
        "level": info.get("assembly_level"),
        "name": info.get("assembly_name"),
        "date": date,
        "submitter": info.get("submitter"),
        "seq_tech": info.get("sequencing_tech") or "",
        "method": info.get("assembly_method") or "",
        "total_len": total,
        "n_contigs": stats.get("number_of_contigs"),
        "contig_n50": stats.get("contig_n50"),
        "n_scaf": stats.get("number_of_scaffolds"),
        "scaf_n50": stats.get("scaffold_n50"),
        "gaps": "",
        "gc": float(stats["gc_percent"]) if stats.get("gc_percent") is not None else "",
        "refseq_cat": info.get("refseq_category") or "",
        "bioproject": info.get("bioproject_accession") or "",
        "year": int(date[:4]) if date[:4].isdigit() else "",
        "platform": platform,
        "lr": long_read,
        "exp_chr": expected_chromosomes(organism, curation),
        "gapless": total is not None and total == ungapped,
        "assembler": assembler,
        "asm_mode": mode,
        "ref_inherited": ref_inherited,
        "contig_class": contig_class,
    }


def select_reports(reports: Iterable[dict], curation: dict) -> list:
    """Current nuclear assemblies: drop superseded versions and organelle-sized records.

    NCBI keeps every version of an assembly; only the current one describes what is deposited,
    apart from the versions listed in ``curation['keep_superseded']``.
    Records below ``min_nuclear_length`` are standalone kinetoplast/maxicircle sequences or
    fragmentary legacy drafts, not nuclear genomes.
    """
    keep = []
    for report in reports:
        status = report.get("assembly_info", {}).get("assembly_status")
        if status != "current" and report["accession"] not in curation["keep_superseded"]:
            continue
        total = _int(report.get("assembly_stats", {}).get("total_sequence_length")) or 0
        if total < curation["min_nuclear_length"]:
            continue
        keep.append(report)
    return keep


def build_table(reports: Iterable[dict], curation: Optional[dict] = None) -> list:
    curation = curation or load_curation()
    return [build_row(r, curation) for r in select_reports(reports, curation)]


def long_read_subset(rows: Iterable[dict], curation: Optional[dict] = None) -> list:
    """GenBank assemblies built with long reads, minus the bioprojects in ``exclude_bioprojects``.

    RefSeq (GCF) rows are left out because each mirrors a GenBank row already present.
    """
    curation = curation or load_curation()
    return [
        row
        for row in rows
        if row["lr"]
        and row["accession"].startswith("GCA_")
        and row["bioproject"] not in curation["exclude_bioprojects"]
    ]


def write_csv(rows: Iterable[dict], path: Path) -> int:
    rows = list(rows)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
