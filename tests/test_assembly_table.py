"""Assembly table rules, on small hand-made NCBI reports (no network)."""

import csv
import json

import pytest
from click.testing import CliRunner

from leishref import assembly_table as at
from leishref.cli import cli


@pytest.fixture(scope="module")
def curation():
    return at.load_curation()


def report(accession, organism="Leishmania donovani", tech=None, method=None, total=33_000_000, **extra):
    info = {
        "assembly_level": "Chromosome",
        "assembly_name": "ASM1",
        "assembly_status": "current",
        "release_date": "2024-09-19",
        "submitter": "Lab",
        "bioproject_accession": "PRJNA1",
    }
    if tech:
        info["sequencing_tech"] = tech
    if method:
        info["assembly_method"] = method
    info.update(extra.pop("info", {}))
    return {
        "accession": accession,
        "organism": {"organism_name": organism, "infraspecific_names": {"strain": "S1"}},
        "assembly_info": info,
        "assembly_stats": {
            "total_sequence_length": str(total),
            "total_ungapped_length": str(total),
            "number_of_contigs": 36,
            "number_of_scaffolds": 36,
            "contig_n50": 1_000_000,
            "scaffold_n50": 1_000_000,
            "gc_percent": 58,
        },
        **extra,
    }


@pytest.mark.parametrize(
    "tech, label, long_read",
    [
        ("Oxford Nanopore GridION", "ONT only", True),
        ("Illumina MiSeq; Oxford Nanopore MinION", "ONT+Illumina", True),
        ("PacBio RS II", "PacBio only", True),
        ("PacBio RSII; Illumina HiSeq", "PacBio+Illumina", True),
        ("Illumina,PacBio", "PacBio+Illumina", True),
        ("454; Illumina GAII", "Illumina only", False),
        ("Roche 454", "unspecified", False),
        (None, "unspecified", False),
    ],
)
def test_platform_of(tech, label, long_read):
    assert at.platform_of(tech) == (label, long_read)


@pytest.mark.parametrize(
    "method, assembler, mode",
    [
        ("Canu v. 1.7; SPAdes v. 3.15", "Canu", "de novo"),
        ("HGAP v. 2; Celera Assembler v. 8.3; CANU v. 1.0", "Canu", "de novo"),
        ("Flye assembler v. 2.6; Samtools v. 1.9", "Flye", "de novo"),
        ("NGSEP v. 4.3.2", "reference-guided", "reference-guided"),
        ("Burrows Wheeler Aligner (BWA-MEM) v0.7.18-r1243", "reference-guided", "reference-guided"),
        ("Megahit v. 1.2.9", "MEGAHIT", "de novo"),
        ("Newbler v. 2.3; Velvet v. 0.7.56", "Newbler / GS De Novo", "de novo"),
        ("various", "other/unclear", "other/unclear"),
        (None, "unstated", "unstated"),
    ],
)
def test_assembler_of(method, assembler, mode):
    assert at.assembler_of(method) == (assembler, mode)


def test_expected_chromosomes(curation):
    assert at.expected_chromosomes("Leishmania braziliensis MHOM/BR/75/M2904", curation) == 35
    assert at.expected_chromosomes("Leishmania cf. guyanensis/panamensis", curation) == 35
    assert at.expected_chromosomes("Leishmania donovani", curation) == 36


def test_selection_drops_superseded_and_organelle_records(curation):
    old = report("GCA_1.1", info={"assembly_status": "previous"})
    kinetoplast = report("GCA_2.1", total=25_000)
    kept = report("GCA_3.1")
    revived = report("GCA_000755165.1", info={"assembly_status": "previous"})
    selected = [r["accession"] for r in at.select_reports([old, kinetoplast, kept, revived], curation)]
    assert selected == ["GCA_3.1", "GCA_000755165.1"]


def test_reference_guided_assembly_inherits_contiguity(curation):
    row = at.build_row(report("GCA_4.1", tech="Oxford Nanopore GridION", method="NGSEP v. 4.3.2"), curation)
    assert row["asm_mode"] == "reference-guided"
    assert row["ref_inherited"] is True
    assert row["contig_class"] == "reference-guided (declared)"


def test_refseq_mirror_inherits_curated_class(curation):
    row = at.build_row(report("GCF_000002725.2", paired_accession="GCA_000002725.2"), curation)
    assert row["contig_class"] == "Sanger reference"


def test_gapless_and_year(curation):
    clean = at.build_row(report("GCA_5.1"), curation)
    gapped = report("GCA_6.1")
    gapped["assembly_stats"]["total_ungapped_length"] = "32999000"
    assert clean["gapless"] is True and clean["year"] == 2024
    assert at.build_row(gapped, curation)["gapless"] is False


def test_long_read_subset_excludes_population_study(curation):
    rows = [
        at.build_row(report("GCA_7.1", tech="PacBio RSII"), curation),
        at.build_row(report("GCA_8.1", tech="Illumina HiSeq"), curation),
        at.build_row(report("GCF_9.1", tech="PacBio RSII"), curation),
        at.build_row(
            report("GCA_10.1", tech="Oxford Nanopore GridION", info={"bioproject_accession": "PRJNA881045"}), curation
        ),
    ]
    assert [r["accession"] for r in at.long_read_subset(rows, curation)] == ["GCA_7.1"]


def test_cli_writes_both_files(tmp_path):
    reports = tmp_path / "reports.json"
    reports.write_text(
        json.dumps({"reports": [report("GCA_11.1", tech="PacBio RSII"), report("GCA_12.1", tech="Illumina HiSeq")]})
    )
    result = CliRunner().invoke(
        cli, ["dev", "assembly-table", "--reports", str(reports), "--outdir", str(tmp_path / "t")]
    )
    assert result.exit_code == 0, result.output
    with open(tmp_path / "t" / "leishmania_nuclear_assemblies.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["accession"] for r in rows] == ["GCA_11.1", "GCA_12.1"]
    assert list(rows[0]) == at.COLUMNS
    with open(tmp_path / "t" / "leishmania_nuclear_assemblies_longread.csv") as fh:
        assert [r["accession"] for r in csv.DictReader(fh)] == ["GCA_11.1"]
