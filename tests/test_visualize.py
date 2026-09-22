import gzip
from pathlib import Path

import matplotlib.axes
import pytest

from leishref.metadata import Genome, write_genome
from leishref.visualize import (
    plot_assembly_level_by_technology,
    plot_chromosome_length_histogram,
    plot_genome_stats,
    plot_sequencing_technology,
)


def _write_genome_with_optional_fasta(
    root: Path,
    identifier: str,
    species: str,
    stats: dict,
    records: dict | None = None,
    fasta_name: str | None = None,
):
    directory = root / "ncbi" / identifier
    directory.mkdir(parents=True, exist_ok=True)

    files = {}
    if records:
        fasta_name = fasta_name or f"{identifier}.fna"
        fasta = directory / fasta_name
        writer = gzip.open if fasta.suffix == ".gz" else open
        with writer(fasta, "wt") as fh:
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
        fasta_name="GCA_10.fasta",
    )
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_11",
        "Leishmania donovani",
        {"num_bases": 100},
        records={"chr1": "A" * 1200, "chr2": "A" * 2500},
        fasta_name="GCA_11.fa.gz",
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


def test_plot_chromosome_length_histogram_species_filter_supports_genus_species_prefix(tmp_path):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_50",
        "Leishmania major strainX",
        {"num_bases": 100},
        records={"chr1": "A" * 1000},
    )

    output = tmp_path / "prefix.png"
    out = plot_chromosome_length_histogram(tmp_path, output, species_filter=["Leishmania major"])

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_chromosome_length_histogram_falls_back_to_vert_boxplot(tmp_path, monkeypatch):
    _write_genome_with_optional_fasta(
        tmp_path,
        "GCA_60",
        "Leishmania major",
        {"num_bases": 100},
        records={"chr1": "A" * 1000},
    )

    original_boxplot = matplotlib.axes.Axes.boxplot

    def patched_boxplot(self, *args, **kwargs):
        if "orientation" in kwargs:
            raise TypeError("unexpected keyword argument 'orientation'")
        return original_boxplot(self, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "boxplot", patched_boxplot)

    output = tmp_path / "fallback.png"
    out = plot_chromosome_length_histogram(tmp_path, output)

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_sequencing_technology_creates_file(tmp_path):
    directory = tmp_path / "ncbi" / "GCA_1"
    directory.mkdir(parents=True, exist_ok=True)
    write_genome(
        directory,
        Genome(
            identifier="GCA_1",
            source="NCBI",
            accession="GCA_1",
            species="Leishmania major",
            provenance={"sequencing_technology": "Illumina HiSeq"},
            stats={"num_bases": 32000000},
        ),
    )

    directory = tmp_path / "ncbi" / "GCA_2"
    directory.mkdir(parents=True, exist_ok=True)
    write_genome(
        directory,
        Genome(
            identifier="GCA_2",
            source="NCBI",
            accession="GCA_2",
            species="Leishmania donovani",
            provenance={"sequencing_technology": "Oxford Nanopore GridION"},
            stats={"num_bases": 33000000},
        ),
    )

    directory = tmp_path / "ncbi" / "GCA_3"
    directory.mkdir(parents=True, exist_ok=True)
    write_genome(
        directory,
        Genome(
            identifier="GCA_3",
            source="NCBI",
            accession="GCA_3",
            species="Leishmania infantum",
            provenance={"sequencing_technology": "PacBio RSII; Illumina HiSeq"},
            stats={"num_bases": 31000000},
        ),
    )

    output = tmp_path / "technology.png"
    out = plot_sequencing_technology(tmp_path, output)

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_assembly_level_by_technology_creates_file(tmp_path):
    directory = tmp_path / "ncbi" / "GCA_1"
    directory.mkdir(parents=True, exist_ok=True)
    write_genome(
        directory,
        Genome(
            identifier="GCA_1",
            source="NCBI",
            accession="GCA_1",
            species="Leishmania major",
            assembly_level="Complete Genome",
            provenance={"sequencing_technology": "Illumina HiSeq"},
            stats={"num_bases": 32000000},
        ),
    )

    directory = tmp_path / "ncbi" / "GCA_2"
    directory.mkdir(parents=True, exist_ok=True)
    write_genome(
        directory,
        Genome(
            identifier="GCA_2",
            source="NCBI",
            accession="GCA_2",
            species="Leishmania donovani",
            assembly_level="Chromosome",
            provenance={"sequencing_technology": "Oxford Nanopore GridION"},
            stats={"num_bases": 33000000},
        ),
    )

    output = tmp_path / "assembly_by_tech.png"
    out = plot_assembly_level_by_technology(tmp_path, output)

    assert out == output
    assert output.exists()
    assert output.stat().st_size > 0
