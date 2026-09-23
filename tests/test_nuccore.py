"""Standalone NCBI nuccore record fetching, with bioservices mocked out."""

import logging

import pytest

from leishref.nuccore import NuccoreError, fetch_nucleotide_fasta, fetch_nucleotide_metadata


class FakeClient:
    def __init__(self, fasta=None, search=None, summary=None):
        self._fasta = fasta
        self._search = search or {}
        self._summary = summary or {}

    def EFetch(self, db, accession, retmode="text", rettype="fasta"):
        return self._fasta

    def ESearch(self, db, accession):
        return self._search

    def ESummary(self, db, uid):
        return self._summary


def test_fetch_nucleotide_fasta_writes_the_file(tmp_path, monkeypatch):
    fasta = b">BK010877.1 TPA_asm: Leishmania infantum kinetoplast\nACGTACGT\n"
    monkeypatch.setattr("leishref.nuccore._client", lambda email=None: FakeClient(fasta=fasta))

    path = fetch_nucleotide_fasta("BK010877.1", tmp_path)

    assert path == tmp_path / "BK010877.1.fasta"
    assert path.read_text() == fasta.decode()


def test_fetch_nucleotide_fasta_raises_when_ncbi_has_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("leishref.nuccore._client", lambda email=None: FakeClient(fasta=""))

    with pytest.raises(NuccoreError, match="no data"):
        fetch_nucleotide_fasta("nonexistent", tmp_path)


def test_fetch_nucleotide_fasta_raises_on_unexpected_response(tmp_path, monkeypatch):
    monkeypatch.setattr("leishref.nuccore._client", lambda email=None: FakeClient(fasta="<html>error</html>"))

    with pytest.raises(NuccoreError, match="Unexpected"):
        fetch_nucleotide_fasta("BK010877.1", tmp_path)


def test_fetch_nucleotide_metadata_parses_esummary(monkeypatch):
    search = {"idlist": ["1751371458"]}
    summary = {
        "1751371458": {
            "accessionversion": "BK010877.1",
            "taxid": 5671,
            "organism": "Leishmania infantum",
            "strain": "JPCM5",
            "title": "TPA_asm: Leishmania infantum strain JPCM5 kinetoplast, complete sequence",
            "createdate": "2019/09/26",
            "slen": 18277,
        }
    }
    monkeypatch.setattr("leishref.nuccore._client", lambda email=None: FakeClient(search=search, summary=summary))

    meta = fetch_nucleotide_metadata("BK010877.1")

    assert meta["accession"] == "BK010877.1"
    assert meta["taxon_id"] == 5671
    assert meta["organism"] == "Leishmania infantum"
    assert meta["strain"] == "JPCM5"
    assert meta["release_date"] == "2019-09-26"
    assert meta["length"] == 18277


def test_fetch_nucleotide_metadata_returns_empty_dict_when_not_found(monkeypatch):
    monkeypatch.setattr("leishref.nuccore._client", lambda email=None: FakeClient(search={"idlist": []}))

    assert fetch_nucleotide_metadata("nonexistent") == {}


def test_client_suppresses_bioservices_missing_email_warning(caplog):
    """EUtils() logs a rate-limit notice whenever no email is configured; we mute it."""
    from leishref.nuccore import _client

    with caplog.at_level(logging.WARNING, logger="bioservices.EUtils"):
        _client()

    assert caplog.records == []
