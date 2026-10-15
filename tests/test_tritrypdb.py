from click.testing import CliRunner

from leishref.cli import cli
from leishref.metadata import catalog
from leishref.tritrypdb import fasta_header_info, species_and_strain

HEADER = ">CM1 | organism=Leishmania_major_strain_Friedlin | version=2016-05-28 | length=12 | SO=chromosome\\n"


def test_species_and_strain():
    assert species_and_strain("Leishmania major strain Friedlin") == ("Leishmania major", "Friedlin")
    assert species_and_strain("Leishmania major Friedlin 2021") == ("Leishmania major", "Friedlin 2021")
    assert species_and_strain("Leishmania sp. Ghana MHOM/GH/2012/GH5") == ("Leishmania sp. Ghana", "MHOM/GH/2012/GH5")
    assert species_and_strain("Leishmania tropica L590") == ("Leishmania tropica", "L590")


def test_fasta_header_info(tmp_path):
    fasta = tmp_path / "a.fasta"
    fasta.write_text(HEADER.replace("\\n", "\n") + "ACGTACGTACGT\n")
    info = fasta_header_info(fasta)
    assert info == {"organism": "Leishmania major strain Friedlin", "version": "2016-05-28", "so": "chromosome"}


def test_import_tritrypdb_writes_one_entry_per_genome(tmp_path):
    staged, root = tmp_path / "staged", tmp_path / "catalog"
    staged.mkdir()
    header = HEADER.replace("\\n", "\n")
    (staged / "TriTrypDB-71_LmajorFriedlin_Genome.fasta").write_text(header + "ACGTACGTACGT\n")
    (staged / "TriTrypDB-71_LmajorFriedlin.gff").write_text("##gff-version 3\n")
    (staged / "TriTrypDB-71_LdonovaniBHU1220_Genome.fasta").write_text(
        header.replace("major_strain_Friedlin", "donovani_strain_BHU_1220") + "ACGT\n"
    )
    result = CliRunner().invoke(
        cli,
        ["dev", "import-tritrypdb", str(staged), "--release", "71", "--doi", "10.5281/zenodo.1",
         "--downloaded", "2026-10-14", "--catalog-dir", str(root)],
    )  # fmt: skip
    assert result.exit_code == 0, result.output

    entries = {g.identifier: g for g in catalog(root)}
    assert set(entries) == {"TriTrypDB-71_LmajorFriedlin", "TriTrypDB-71_LdonovaniBHU1220"}
    major = entries["TriTrypDB-71_LmajorFriedlin"]
    assert major.path == root / "tritrypdb" / "71" / "TriTrypDB-71_LmajorFriedlin"
    assert major.zenodo_doi == "10.5281/zenodo.1"
    assert major.gff == "TriTrypDB-71_LmajorFriedlin.gff"
    assert major.strain == "Friedlin" and major.taxon_id == 5664
    assert major.tritrypdb["release"] == 71
    assert major.license["name"] and major.access == {"downloadable": True}
    assert entries["TriTrypDB-71_LdonovaniBHU1220"].gff is None
