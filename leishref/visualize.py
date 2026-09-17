"""Visualization tools for genome statistics."""

from pathlib import Path
from typing import Optional, List
import matplotlib.pyplot as plt
import seaborn as sns
from leishref.metadata import catalog, CATALOG_DIR


def plot_genome_sizes(
    catalog_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    species_filter: Optional[List[str]] = None,
    include_kinetoplast: bool = False,
) -> Path:
    """Plot genome sizes by species.

    Args:
        catalog_dir: Catalog directory (default: CATALOG_DIR)
        output_path: Save plot to this path (default: genomes_by_size.png)
        species_filter: Plot only these species (optional)
        include_kinetoplast: Include kinetoplast-only genomes (default: False)

    Returns:
        Path to saved plot
    """
    entries = catalog(catalog_dir)
    ncbi = [g for g in entries if g.source == "NCBI" and g.accession and g.stats and g.stats.get("num_bases")]

    # Filter out small genomes (kinetoplast-only, < 1 Mb) by default
    if not include_kinetoplast:
        ncbi = [g for g in ncbi if g.stats.get("num_bases", 0) >= 1_000_000]

    if species_filter:
        ncbi = [g for g in ncbi if any(s.lower() in (g.species or "").lower() for s in species_filter)]

    if not ncbi:
        raise ValueError("No NCBI genomes with size data found")

    # Sort by species then size
    ncbi = sorted(ncbi, key=lambda g: (g.species or "", g.stats.get("num_bases", 0)))

    fig, ax = plt.subplots(figsize=(12, max(6, len(ncbi) / 3)))

    species_labels = [g.species or "?" for g in ncbi]
    sizes = [g.stats.get("num_bases", 0) / 1e6 for g in ncbi]  # Convert to Mb

    # Color by species
    species_set = sorted(set(species_labels))
    colors = sns.color_palette("husl", len(species_set))
    color_map = {sp: colors[i] for i, sp in enumerate(species_set)}
    bar_colors = [color_map[sp] for sp in species_labels]

    ax.barh(range(len(ncbi)), sizes, color=bar_colors)
    ax.set_yticks(range(len(ncbi)))
    ax.set_yticklabels([f"{sp.split()[-1] if ' ' in sp else sp} ({g.accession})" for sp, g in zip(species_labels, ncbi)], fontsize=9)
    ax.set_xlabel("Genome size (Mb)", fontsize=11)
    ax.set_title("Leishmania Genome Sizes", fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)

    if output_path is None:
        output_path = Path("genomes_by_size.png")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def plot_genome_size_histogram(
    catalog_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    include_kinetoplast: bool = False,
) -> Path:
    """Plot histogram of genome sizes.

    Args:
        catalog_dir: Catalog directory (default: CATALOG_DIR)
        output_path: Save plot to this path (default: genome_size_histogram.png)
        include_kinetoplast: Include kinetoplast-only genomes (default: False)

    Returns:
        Path to saved plot
    """
    entries = catalog(catalog_dir)
    ncbi = [g for g in entries if g.source == "NCBI" and g.accession and g.stats and g.stats.get("num_bases")]

    if not include_kinetoplast:
        ncbi = [g for g in ncbi if g.stats.get("num_bases", 0) >= 1_000_000]

    if not ncbi:
        raise ValueError("No NCBI genomes with size data found")

    sizes = [g.stats.get("num_bases", 0) / 1e6 for g in ncbi]  # Convert to Mb

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(sizes, bins=15, color="steelblue", edgecolor="black", alpha=0.7)
    ax.set_xlabel("Genome size (Mb)", fontsize=11)
    ax.set_ylabel("Number of genomes", fontsize=11)
    ax.set_title(f"Distribution of Leishmania Genome Sizes (n={len(ncbi)})", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    if output_path is None:
        output_path = Path("genome_size_histogram.png")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def plot_genome_stats(
    catalog_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Plot multiple genome statistics: size, scaffolds, contigs, N50.

    Returns:
        Path to saved plot
    """
    entries = catalog(catalog_dir)
    ncbi = [g for g in entries if g.source == "NCBI" and g.accession and g.stats]

    if not ncbi:
        raise ValueError("No NCBI genomes found")

    # Group by species
    by_species = {}
    for g in ncbi:
        sp = g.species or "Unknown"
        if sp not in by_species:
            by_species[sp] = []
        by_species[sp].append(g)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    axes = axes.flatten()

    species_names = sorted(by_species.keys())
    species_short = [s.split()[-1][:3] for s in species_names]  # Last word, first 3 chars

    # Genome size
    sizes = [[g.stats.get("num_bases", 0) / 1e6 for g in by_species[sp]] for sp in species_names]
    axes[0].boxplot(sizes, tick_labels=species_short)
    axes[0].set_ylabel("Genome size (Mb)")
    axes[0].set_title("Genome Size Distribution")
    axes[0].tick_params(axis="x", rotation=45)

    # Scaffolds
    scaffolds = [[max(g.stats.get("num_scaffolds", 0), 1) for g in by_species[sp]] for sp in species_names]
    axes[1].boxplot(scaffolds, tick_labels=species_short)
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Number of scaffolds (log scale)")
    axes[1].set_title("Scaffold Count Distribution")
    axes[1].tick_params(axis="x", rotation=45)

    # Contigs
    contigs = [[max(g.stats.get("num_contigs", 0), 1) for g in by_species[sp]] for sp in species_names]
    axes[2].boxplot(contigs, tick_labels=species_short)
    axes[2].set_yscale("log")
    axes[2].set_ylabel("Number of contigs (log scale)")
    axes[2].set_title("Contig Count Distribution")
    axes[2].tick_params(axis="x", rotation=45)

    # Scaffold N50
    scaffold_n50 = [[g.stats.get("scaffold_n50", 0) / 1e6 for g in by_species[sp]] for sp in species_names]
    axes[3].boxplot(scaffold_n50, tick_labels=species_short)
    axes[3].set_ylabel("Scaffold N50 (Mb)")
    axes[3].set_title("Scaffold N50 Distribution")
    axes[3].tick_params(axis="x", rotation=45)

    plt.tight_layout()

    if output_path is None:
        output_path = Path("genome_stats.png")

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def _iter_fasta_lengths(fasta_path: Path):
    """Yield FASTA record lengths from a local genome file."""
    current = 0
    started = False

    with open(fasta_path, "r") as handle:
        for line in handle:
            if line.startswith(">"):
                if started:
                    yield current
                current = 0
                started = True
            else:
                current += len(line.strip())

    if started:
        yield current


def plot_chromosome_length_histogram(
    catalog_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    species_filter: Optional[List[str]] = None,
) -> Path:
    """Plot histogram + boxplot of chromosome/sequence lengths from local FASTA files."""
    entries = catalog(catalog_dir)
    lengths = []

    for genome in entries:
        if species_filter and not any(s.lower() in (genome.species or "").lower() for s in species_filter):
            continue
        fasta_name = genome.fasta
        if not fasta_name or genome.path is None:
            continue
        fasta_path = genome.path / fasta_name
        if not fasta_path.is_file():
            continue
        lengths.extend([length / 1e6 for length in _iter_fasta_lengths(fasta_path) if length > 0])

    if not lengths:
        raise ValueError("No local FASTA files found; use a local catalog/database with installed genomes")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [4, 1]}, sharex=True)

    axes[0].hist(lengths, bins=min(40, max(10, len(lengths) // 5)), color="slateblue", edgecolor="black", alpha=0.75)
    axes[0].set_ylabel("Number of chromosomes/sequences", fontsize=11)
    axes[0].set_title(f"Chromosome Length Distribution (n={len(lengths)})", fontsize=12, fontweight="bold")
    axes[0].grid(axis="y", alpha=0.3)

    axes[1].boxplot(lengths, orientation="horizontal", patch_artist=True, boxprops={"facecolor": "lavender"})
    axes[1].set_xlabel("Chromosome length (Mb)", fontsize=11)
    axes[1].set_yticks([])
    axes[1].grid(axis="x", alpha=0.3)

    if output_path is None:
        output_path = Path("chromosome_length_histogram.png")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path
