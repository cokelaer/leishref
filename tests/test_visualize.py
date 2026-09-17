from pathlib import Path

import pytest

from leishref.metadata import Genome, write_genome
from leishref.visualize import plot_chromosome_length_histogram, plot_genome_stats


def _write_genome_with_optional_fasta(
    root: Path,
    identifier: str,
    species: str,
    stats: dict,
    records: dict | None = None,
):
    directory = root / "ncbi" / identifier
    directory.mkdir(parents=True, exist_ok=True)

    files = {}
    if records:
        fasta_name = f"{identifier}.fna"
        fasta = directory / fasta_name
        with open(fasta, "w") as fh:
            for name, seq in records.items():
                fh.write(f">{name}\n{seq}\n")
        files["fasta"] = fasta_name

    write_genome(
        directory,
        Genome(
            identifier=identifier,
            source="NCBI",
            accession=identifier,
            species=species,
            stats=stats,
            files=files,
        ),
    )


def test_plot_genome_stats_creates_file(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_1",
        "Leishmania major",
        {"num_bases": 32000000, "num_scaffolds": 36, "num_contigs": 50, "scaffold_n50": 900000},
    )
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_2",
        "Leishmania major",
        {"num_bases": 33000000, "num_scaffolds": 40, "num_contigs": 120, "scaffold_n50": 700000},
    )
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_3",
        "Leishmania donovani",
        {"num_bases": 31000000, "num_scaffolds": 36, "num_contigs": 60, "scaffold_n50": 850000},
    )

    output = tmp_path / "stats.png"
    out = plot_genome_stats(tmp_path, output)

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_chromosome_length_histogram_creates_file(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_10",
        "Leishmania major",
        {"num_bases": 100},
        records={"chr1": "A" * 1000, "chr2": "A" * 2000, "chr3": "A" * 1500},
    )
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_11",
        "Leishmania donovani",
        {"num_bases": 100},
        records={"chr1": "A" * 1200, "chr2": "A" * 2500},
    )

    output = tmp_path / "chromosome_hist.png"
    out = plot_chromosome_length_histogram(tmp_path, output)

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_chromosome_length_histogram_requires_fasta(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_20",
        "Leishmania major",
        {"num_bases": 100},
        records=None,
    )

    with pytest.raises(ValueError, match="No local FASTA files found"):
        plot_chromosome_length_histogram(tmp_path, tmp_path / "out.png")


def test_plot_chromosome_length_histogram_applies_species_filter(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_30",
        "Leishmania major",
        {"num_bases": 100},
        records=None,
    )
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_31",
        "Leishmania donovani",
        {"num_bases": 100},
        records={"chr1": "A" * 1200, "chr2": "A" * 2500},
    )

    with pytest.raises(ValueError, match="No local FASTA files found"):
        plot_chromosome_length_histogram(tmp_path, tmp_path / "filtered.png", species_filter=["major"])


def test_plot_chromosome_length_histogram_species_filter_is_token_based(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_40",
        "Leishmania majori",
        {"num_bases": 100},
        records={"chr1": "A" * 1000},
    )

    with pytest.raises(ValueError, match="No local FASTA files found"):
        plot_chromosome_length_histogram(tmp_path, tmp_path / "filtered2.png", species_filter=["major"])
