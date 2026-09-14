"""Suggested aliases: <Lspec>.<source>.<discriminator>."""

import pytest

from leishref.metadata import Genome, catalog
from leishref.naming import source_tag, species_abbrev, strain_from_assembly_name, suggest_alias


def genome(**kw):
    base = {"identifier": "GCA_1.1", "source": "NCBI", "species": "Leishmania tropica"}
    base.update(kw)
    return Genome(**base)


@pytest.mark.parametrize(
    "species,expected",
    [("Leishmania tropica", "Ltrop"), ("Leishmania donovani", "Ldono"), (None, "Unk")],
)
def test_species_abbrev(species, expected):
    assert species_abbrev(species) == expected


def test_close_species_do_not_collapse():
    assert species_abbrev("Leishmania tropica") != species_abbrev("Leishmania turanica")


def test_source_tag_folds_in_tritrypdb_release():
    assert source_tag("TriTrypDB", "68") == "tritryp68"
    assert source_tag("NCBI", "68") == "ncbi", "NCBI accessions already carry a version"
    assert source_tag("Zenodo") == "zenodo"


def test_opaque_assembly_names_are_rejected():
    assert strain_from_assembly_name("ASM22713v2", "Leishmania donovani") is None


def test_strain_recovered_from_assembly_name():
    assert strain_from_assembly_name("Leishmania_tropica_L590-2.0.2", "Leishmania tropica") == "L590"


def test_stray_whitespace_is_normalised():
    """NCBI ships 'MHOM_LB _2017_IK', a space next to an underscore."""
    assert strain_from_assembly_name("MHOM_LB _2017_IK", "Leishmania tropica") == "MHOM_LB_2017_IK"


def test_strain_beats_assembly_name():
    assert suggest_alias(genome(strain="JPCM5", assembly_name="ASM287v2")) == "Ltrop.ncbi.JPCM5"


def test_accession_used_when_nothing_is_informative():
    suggested = suggest_alias(genome(assembly_name="ASM22713v2", accession="GCA_000227135.2"))
    assert suggested == "Ltrop.ncbi.GCA_000227135.2"


def test_published_assembly_names_itself_from_its_identifier():
    suggested = suggest_alias(
        genome(identifier="Ltropica.Ld1S.scaffold.pecat.filtered", source="Zenodo", species="Leishmania tropica")
    )
    assert suggested == "Ltrop.zenodo.pecat_filtered"


def test_every_catalog_genome_yields_a_usable_suggestion():
    suggestions = [suggest_alias(g) for g in catalog()]
    assert all(s and " " not in s and s.count(".") >= 2 for s in suggestions)


def test_suggestions_are_unique_across_the_catalog():
    suggestions = [suggest_alias(g) for g in catalog()]
    assert len(set(suggestions)) == len(suggestions)
