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


#: Open nomenclature markers. What follows one of these is part of the taxon name, not
#: a strain: "Leishmania sp. Ghana" and "Leishmania sp. Namibia" are different organisms.
OPEN_NOMENCLATURE = ("sp.", "cf.", "aff.", "nr.")


def species_from_organism(organism_name) -> str:
    """The species part of an NCBI organism name.

    organism_name often carries more than the binomial ("Leishmania infantum JPCM5"), so
    normally the first two tokens are the species. An undescribed species is named by
    what follows the marker, so that word is kept too, otherwise every unplaced isolate
    in the genus collapses into a single "Leishmania sp.".
    """
    tokens = (organism_name or "").split()
    if len(tokens) < 2:
        return " ".join(tokens)
    if tokens[1].lower() in OPEN_NOMENCLATURE and len(tokens) > 2:
        return " ".join(tokens[:3])
    return " ".join(tokens[:2])


def strain_from_organism(organism_name) -> str:
    """Whatever follows the species in an NCBI organism name, or "".

    NCBI names an infraspecific taxon after its strain ("Leishmania infantum JPCM5"),
    and for those assemblies infraspecific_names is often empty, so the organism name
    is the only place the strain appears.
    """
    organism_name = organism_name or ""
    species = species_from_organism(organism_name)
    return organism_name[len(species) :].strip()


def _parse_summary(data: dict) -> dict:
    """Pull the fields we keep out of one `datasets summary` record."""
    info = data.get("assembly_info", {})
    organism = data.get("organism", {})
    # NCBI records the strain under infraspecific_names, not in organism_name. Where a
    # submitter registered a WHO designation as an isolate, strain is empty instead, and
    # for an infraspecific taxon both are empty and only organism_name carries it.
    infraspecific = organism.get("infraspecific_names") or {}
    return {
        "accession": data.get("accession"),
        "taxon_id": organism.get("tax_id"),
        "organism_name": organism.get("organism_name"),
        "strain": (
            infraspecific.get("strain")
            or infraspecific.get("isolate")
            or strain_from_organism(organism.get("organism_name"))
            or None
        ),
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


def _summary(accessions: list, report: Optional[str] = None) -> list:
    """Run `datasets summary` for one batch of accessions."""
    cmd = ["datasets", "summary", "genome", "accession", *accessions]
    if report:
        cmd.extend(["--report", report])
    cmd.append("--as-json-lines")
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


def _iter_sequence_records(node):
    """Yield sequence report records from nested datasets JSON structures."""
    if isinstance(node, list):
        for item in node:
            yield from _iter_sequence_records(item)
        return

    if not isinstance(node, dict):
        return

    record_keys = {
        "genbank_accession",
        "refseq_accession",
        "assigned_molecule",
        "assigned_molecule_location_type",
        "chromosome",
        "chr_name",
        "sequence_name",
    }
    if record_keys.intersection(node.keys()):
        yield node

    for value in node.values():
        yield from _iter_sequence_records(value)


def _coalesce(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _looks_like_maxicircle(record: dict) -> bool:
    text = str(
        _coalesce(record.get("role"), record.get("sequence_role"), record.get("sequence_name"), record.get("name"), "")
    ).lower()
    return any(token in text for token in ("maxicircle", "kinetoplast", "mitochond"))


def _chromosome_label(record: dict, fallback: str) -> str:
    assigned = _coalesce(
        record.get("chr_name"),
        record.get("chromosome"),
        record.get("assigned_molecule"),
        record.get("assigned_molecule_name"),
    )
    if assigned in (None, ""):
        return fallback

    assigned_text = str(assigned).strip()
    if assigned_text.lower().startswith("chromosome"):
        return assigned_text

    location = str(record.get("assigned_molecule_location_type") or "").lower()
    role = str(_coalesce(record.get("role"), record.get("sequence_role"), "")).lower()
    if "chromosome" in location or "chromosome" in role:
        return f"chromosome {assigned_text}"
    return assigned_text


def _pick_primary_sequence_accession(record: dict, assembly_accession: str) -> Optional[str]:
    genbank = record.get("genbank_accession")
    refseq = record.get("refseq_accession")
    raw = record.get("accession")

    if assembly_accession.startswith("GCF_"):
        return _coalesce(refseq, genbank, raw)
    if assembly_accession.startswith("GCA_"):
        return _coalesce(genbank, refseq, raw)
    return _coalesce(raw, genbank, refseq)


def _parse_roman_numeral(value: str) -> Optional[int]:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    token = (value or "").strip().upper()
    if not token or any(ch not in values for ch in token):
        return None
    total = 0
    previous = 0
    for char in reversed(token):
        current = values[char]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    if total <= 0:
        return None
    return total if _to_roman(total) == token else None


def _to_roman(value: int) -> str:
    numerals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    n = value
    for number, symbol in numerals:
        while n >= number:
            out.append(symbol)
            n -= number
    return "".join(out)


def _sequence_index(record: dict, label: str) -> Optional[int]:
    assigned = str(
        _coalesce(
            record.get("assigned_molecule"),
            record.get("chr_name"),
            record.get("chromosome"),
            "",
        )
    ).strip()
    token = assigned or label.replace("chromosome", "", 1).strip()

    if token.isdigit():
        return int(token)
    return _parse_roman_numeral(token)


def _parse_sequence_correspondence(sequence_summary: list, assembly_accession: str) -> list[dict]:
    """Build chromosome correspondence entries from datasets sequence report records."""
    entries = []
    seen = set()
    for record in sequence_summary:
        for sequence in _iter_sequence_records(record):
            accession = _pick_primary_sequence_accession(sequence, assembly_accession)
            if not accession or accession in seen:
                continue

            seen.add(accession)
            name = "maxicircle" if _looks_like_maxicircle(sequence) else _chromosome_label(sequence, accession)
            index = _sequence_index(sequence, name)

            entry = {"accession": accession, "index": index, "name": name}

            genbank = sequence.get("genbank_accession")
            refseq = sequence.get("refseq_accession")
            if genbank:
                entry["genbank_accession"] = genbank
            if refseq:
                entry["refseq_accession"] = refseq
            if name == "maxicircle":
                entry["type"] = "maxicircle"

            entries.append(entry)

    entries.sort(
        key=lambda item: (
            item["index"] is None,
            item["index"] if item["index"] is not None else 10**9,
            item.get("name", ""),
            item["accession"],
        )
    )

    used_indexes = set()
    for entry in entries:
        index = entry["index"]
        if index is None or index in used_indexes:
            entry["index"] = None
            continue
        used_indexes.add(index)

    next_fallback_index = 1
    for entry in entries:
        if entry["index"] is not None:
            continue
        while next_fallback_index in used_indexes:
            next_fallback_index += 1
        entry["index"] = next_fallback_index
        used_indexes.add(next_fallback_index)
        next_fallback_index += 1

    return sorted(entries, key=lambda item: (item["index"], item["accession"]))


def fetch_chromosome_correspondence(accession: str) -> list[dict]:
    """Fetch GenBank/RefSeq-to-chromosome correspondence for one assembly accession."""
    records = _summary([accession], report="sequence")
    if not records:
        return []
    return _parse_sequence_correspondence(records, accession)


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
