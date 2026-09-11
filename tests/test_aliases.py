"""Test alias resolution."""

import tempfile
from pathlib import Path

import pytest

from leishdb.aliases import Aliases


def test_aliases_add_and_resolve():
    """Add alias and resolve it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aliases_path = Path(tmpdir) / "aliases.csv"
        aliases = Aliases(aliases_path)

        aliases.add("Ld1S", "GCA_000410715.1_Leishmania_donovani_Ld1S_genomic.fna")
        assert aliases.resolve("Ld1S") == "GCA_000410715.1_Leishmania_donovani_Ld1S_genomic.fna"


def test_aliases_resolve_missing_returns_input():
    """Resolve missing alias returns input as-is."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aliases_path = Path(tmpdir) / "aliases.csv"
        aliases = Aliases(aliases_path)

        result = aliases.resolve("UnknownAlias")
        assert result == "UnknownAlias"


def test_aliases_contains():
    """Check if alias exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aliases_path = Path(tmpdir) / "aliases.csv"
        aliases = Aliases(aliases_path)

        aliases.add("Ld1S", "GCA_000410715.1_Leishmania_donovani_Ld1S_genomic.fna")
        assert "Ld1S" in aliases
        assert "Unknown" not in aliases


def test_aliases_persist():
    """Aliases persist across instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aliases_path = Path(tmpdir) / "aliases.csv"

        a1 = Aliases(aliases_path)
        a1.add("Ld1S", "file1.fa")
        a1.add("Ltropica", "file2.fa")

        a2 = Aliases(aliases_path)
        assert a2.resolve("Ld1S") == "file1.fa"
        assert a2.resolve("Ltropica") == "file2.fa"
