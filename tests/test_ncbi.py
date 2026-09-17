import leishref.ncbi as ncbi
from leishref.chromosomes import get_chromosome_info, save_chromosome_map


def test_parse_sequence_correspondence_prefers_genbank_for_gca():
    records = [
        {
            "reports": [
                {
                    "genbank_accession": "CP000001.1",
                    "refseq_accession": "NC_000001.1",
                    "assigned_molecule": "1",
                    "assigned_molecule_location_type": "Chromosome",
                },
                {
                    "genbank_accession": "CP000037.1",
                    "refseq_accession": "NC_000037.1",
                    "sequence_name": "kinetoplast maxicircle DNA",
                },
            ]
        }
    ]
    parsed = ncbi._parse_sequence_correspondence(records, "GCA_123456789.1")
    assert parsed[0]["accession"] == "CP000001.1"
    assert parsed[0]["name"] == "chromosome 1"
    assert parsed[0]["refseq_accession"] == "NC_000001.1"
    assert parsed[1]["accession"] == "CP000037.1"
    assert parsed[1]["name"] == "maxicircle"
    assert parsed[1]["type"] == "maxicircle"


def test_parse_sequence_correspondence_prefers_refseq_for_gcf():
    records = [
        {
            "reports": [
                {
                    "genbank_accession": "CP000001.1",
                    "refseq_accession": "NC_000001.1",
                    "assigned_molecule": "1",
                    "assigned_molecule_location_type": "Chromosome",
                }
            ]
        }
    ]
    parsed = ncbi._parse_sequence_correspondence(records, "GCF_123456789.1")
    assert parsed[0]["accession"] == "NC_000001.1"


def test_fetch_chromosome_correspondence_uses_sequence_report(monkeypatch):
    seen = {}

    def fake_summary(accessions, report=None):
        seen["accessions"] = accessions
        seen["report"] = report
        return [
            {
                "reports": [
                    {
                        "genbank_accession": "CP000001.1",
                        "assigned_molecule": "1",
                        "assigned_molecule_location_type": "Chromosome",
                    }
                ]
            }
        ]

    monkeypatch.setattr(ncbi, "_summary", fake_summary)
    parsed = ncbi.fetch_chromosome_correspondence("GCA_123456789.1")
    assert seen == {"accessions": ["GCA_123456789.1"], "report": "sequence"}
    assert parsed[0]["name"] == "chromosome 1"


def test_parse_sequence_correspondence_uses_chromosome_number_for_index():
    records = [
        {
            "reports": [
                {
                    "genbank_accession": "CP000002.1",
                    "assigned_molecule": "2",
                    "assigned_molecule_location_type": "Chromosome",
                },
                {
                    "genbank_accession": "CP000001.1",
                    "assigned_molecule": "1",
                    "assigned_molecule_location_type": "Chromosome",
                },
            ]
        }
    ]
    parsed = ncbi._parse_sequence_correspondence(records, "GCA_123456789.1")
    by_accession = {entry["accession"]: entry["index"] for entry in parsed}
    assert by_accession["CP000001.1"] == 1
    assert by_accession["CP000002.1"] == 2


def test_get_chromosome_info_falls_back_to_paired_accession(tmp_path):
    save_chromosome_map({"GCA_123.1": [{"accession": "CP1.1", "index": 1, "name": "chromosome 1"}]}, tmp_path)
    parsed = get_chromosome_info("GCF_123.1", tmp_path)
    assert parsed and parsed[0]["accession"] == "CP1.1"


def test_invalid_roman_chromosome_token_is_not_interpreted_as_index():
    assert ncbi._parse_roman_numeral("IC") is None
