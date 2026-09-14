"""Alias generation: <Lspec>.<source>.<discriminator>."""

import pytest

from leishref.alias import (
    assign_aliases,
    discriminator,
    make_alias,
    source_tag,
    species_abbrev,
    strain_from_assembly_name,
    unique_alias,
)
from leishref.manifest import CATALOG_PATH, Manifest


def row(**kw):
    base = {"filename": "x.fa", "source": "NCBI", "species": "Leishmania tropica"}
    base.update(kw)
    return base


@pytest.mark.parametrize(
    "species,expected",
    [
        ("Leishmania tropica", "Ltrop"),
        ("Leishmania donovani", "Ldono"),
        ("Leishmania infantum", "Linfa"),
        ("Leishmania major", "Lmajo"),
        ("LtropicaCDC", "Ltrop"),
        (None, "Unk"),
    ],
)
def test_species_abbrev(species, expected):
    assert species_abbrev(species) == expected


def test_species_abbrev_separates_similar_epithets():
    """tropica and turanica must not collapse onto one another."""
    assert species_abbrev("Leishmania tropica") != species_abbrev("Leishmania turanica")


def test_source_tag_folds_in_tritrypdb_release():
    assert source_tag("TriTrypDB", "68") == "tritryp68"
    assert source_tag("TriTrypDB", None) == "tritryp"
    assert source_tag("NCBI", "68") == "ncbi", "NCBI accessions already carry a version"
    assert source_tag("MyAssembly") == "mine"


def test_opaque_assembly_names_are_rejected():
    """ASM<n>v<n> is auto-generated and says less than the accession."""
    for name in ("ASM22713v2", "ASM3717806v1", "asm287v2"):
        assert strain_from_assembly_name(name, "Leishmania donovani") is None


def test_strain_recovered_from_assembly_name():
    assert strain_from_assembly_name("Leishmania_tropica_L590-2.0.2", "Leishmania tropica") == "L590"
    assert strain_from_assembly_name("LDHU3_new", "Leishmania donovani") == "LDHU3_new"


def test_stray_whitespace_is_normalised():
    """NCBI really does ship 'MHOM_LB _2017_IK', space adjacent to underscore."""
    assert strain_from_assembly_name("MHOM_LB _2017_IK", "Leishmania tropica") == "MHOM_LB_2017_IK"


def test_alias_prefers_strain_over_assembly_name():
    assert make_alias(row(strain="JPCM5", assembly_name="ASM287v2")) == "Ltrop.ncbi.JPCM5"


def test_alias_falls_back_to_accession_when_nothing_informative():
    assert make_alias(row(assembly_name="ASM22713v2", accession="GCA_000227135.2")) == "Ltrop.ncbi.GCA_000227135.2"


def test_local_assembly_discriminator_comes_from_filename():
    """Assembler and filtering are only recorded in the filename."""
    assert discriminator(row(source="MyAssembly", filename="Ltropica.Ld1S.scaffold.flye.fasta")) == "flye"
    assert (
        discriminator(row(source="MyAssembly", filename="Ltropica.Ld1S.scaffold.pecat.filtered.fasta"))
        == "pecat_filtered"
    )


def test_unique_alias_falls_back_to_accession_then_counter():
    taken = {"Ltrop.ncbi.CDC"}
    assert unique_alias(row(strain="CDC", accession="GCA_9.1"), taken) == "Ltrop.ncbi.CDC.GCA_9.1"
    assert unique_alias(row(strain="CDC"), taken) == "Ltrop.ncbi.CDC.2"


def test_assign_aliases_keeps_existing_unless_overwriting():
    rows = [row(filename="a.fa", alias="Keep.me", strain="S1"), row(filename="b.fa", strain="S2")]
    assigned = assign_aliases(rows)
    assert assigned["a.fa"] == "Keep.me"
    assert assigned["b.fa"] == "Ltrop.ncbi.S2"

    overwritten = assign_aliases(rows, overwrite=True)
    assert overwritten["a.fa"] == "Ltrop.ncbi.S1"


def test_assign_aliases_is_collision_free():
    rows = [row(filename=f"{i}.fa", strain="SAME") for i in range(4)]
    assigned = assign_aliases(rows, overwrite=True)
    assert len(set(assigned.values())) == 4


def test_shipped_catalog_aliases_are_present_and_unique():
    rows = Manifest(CATALOG_PATH).read()
    aliases = [r["alias"] for r in rows]
    assert all(aliases), "every catalog row should carry an alias"
    assert len(set(aliases)) == len(aliases)
