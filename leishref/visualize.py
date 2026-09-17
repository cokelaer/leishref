"""Visualization tools for genome statistics."""

from pathlib import Path
from typing import List, Optional

from leishref.metadata import catalog


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
    import matplotlib.pyplot as plt
    import seaborn as sns

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
    ax.set_yticklabels(
        [f"{sp.split()[-1] if ' ' in sp else sp} ({g.accession})" for sp, g in zip(species_labels, ncbi)], fontsize=9
    )
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
    import matplotlib.pyplot as plt

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
    """Plot multiple genome statistics: size, contig count, GC%.

    Returns:
        Path to saved plot
    """
    import matplotlib.pyplot as plt

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

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    species_names = sorted(by_species.keys())
    species_short = [s.split()[-1][:3] for s in species_names]  # Last word, first 3 chars

    # Size
    sizes = [[g.stats.get("num_bases", 0) / 1e6 for g in by_species[sp]] for sp in species_names]
    axes[0].boxplot(sizes, labels=species_short)
    axes[0].set_ylabel("Genome size (Mb)")
    axes[0].set_title("Genome Size Distribution")
    axes[0].tick_params(axis="x", rotation=45)

    # Contigs
    contigs = [[g.stats.get("num_contigs", 0) for g in by_species[sp]] for sp in species_names]
    axes[1].boxplot(contigs, labels=species_short)
    axes[1].set_ylabel("Number of contigs")
    axes[1].set_title("Contig Count Distribution")
    axes[1].tick_params(axis="x", rotation=45)

    # GC%
    gc_pcts = [[g.stats.get("gc_percent", 0) for g in by_species[sp]] for sp in species_names]
    axes[2].boxplot(gc_pcts, labels=species_short)
    axes[2].set_ylabel("GC percentage (%)")
    axes[2].set_title("GC Content Distribution")
    axes[2].tick_params(axis="x", rotation=45)

    plt.tight_layout()

    if output_path is None:
        output_path = Path("genome_stats.png")

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path
