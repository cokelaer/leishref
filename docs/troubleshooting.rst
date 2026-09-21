Troubleshooting
================

``--alias is required``
------------------------

::

    $ leishref install GCA_000410715.1
    --alias is required: it names the cached genome,
    becoming the directory under ~/.config/leishref/ and the symlink name.

      leishref install GCA_000410715.1 --alias Ltrop.L590

``leishref install`` always needs an explicit local name, since the accession or
catalog identifier is rarely what you want typed (or read) elsewhere. The command
prints a suggested alias — from ``leishref/data/aliases.txt`` if the accession has
a shorthand, otherwise a name derived from species and strain — so the fix is
usually to copy the suggested command as-is.

``datasets download failed`` / NCBI fetch returns nothing
-------------------------------------------------------------

Commands that touch NCBI assemblies (``install`` for an NCBI accession,
``dev fetch-genome``, ``dev checksum``, ``install-ncbi``) shell out to NCBI's
``datasets`` CLI. If it isn't installed or isn't on ``PATH``, every one of those
commands fails. (``dev fetch-nucleotide`` is unaffected - it goes through
bioservices EUtils instead, see below.)

Check it's available::

    datasets version

If missing, install it (see NCBI's `datasets CLI docs
<https://www.ncbi.nlm.nih.gov/datasets/docs/v2/download-and-install/>`_) or, per this
project's convention, activate the shared bioinformatics environment first::

    damona activate sequana_tools

A genome that legitimately has no NCBI data (withdrawn, suppressed, or a typo'd
accession) prints ``NCBI has no data for <accession>`` rather than a stack trace —
double-check the accession against `NCBI Datasets
<https://www.ncbi.nlm.nih.gov/datasets/>`_ if you see this.

``NCBI nuccore has no data for <accession>``
--------------------------------------------------

``dev fetch-nucleotide`` doesn't use ``datasets`` at all - it goes through
`bioservices <https://bioservices.readthedocs.io/>`_'s EUtils wrapper against
NCBI's ``nuccore`` database, so it needs ``bioservices`` installed
(``poetry install`` pulls it in as a regular dependency) rather than the
``datasets`` CLI. This error means the accession genuinely isn't a nuccore
record - it's most likely a GCA/GCF assembly accession instead, which belongs to
``dev fetch-genome`` (``ncbi/``), not ``dev fetch-nucleotide``
(``ncbi_nucleotide/``) - see :doc:`catalog`.

``ragtag.py not found in PATH or conda envs``
--------------------------------------------------

``leishref dev scaffold`` shells out to RagTag. It looks in three places, in order:
``ragtag.py`` on ``PATH``, ``ragtag`` on ``PATH``, then
``~/miniconda3/envs/py311/bin/ragtag.py`` as a last-resort fallback (this project
keeps RagTag in a dedicated ``py311`` conda env rather than the shared
``sequana_tools`` env — see ``leishref/scaffold.py:find_ragtag_bin()``). If none of
those exist, install RagTag in one of them::

    conda activate py311
    pip install ragtag

``ZENODO_TOKEN env var not set``
--------------------------------------

``leishref dev publish`` needs a personal access token from Zenodo (or
sandbox.zenodo.org for testing)::

    export ZENODO_TOKEN=your-production-token          # zenodo.org
    export ZENODO_SANDBOX_TOKEN=your-sandbox-token      # sandbox.zenodo.org, with --sandbox

Create a token under your Zenodo account's Applications settings with the
``deposit:write`` and ``deposit:actions`` scopes. Run ``dev publish`` without
``--confirm`` first — it's a dry run that shows what would upload, so you can catch
a missing token before anything is actually deposited.

``<link> exists and is not a symlink``
--------------------------------------------

``install``, ``dev add``, ``dev scaffold`` and ``link`` all try to create an
alias-named symlink (e.g. ``Ld1S.fna``) in the current directory. If a *regular*
file already has that name, leishref refuses to overwrite it rather than guessing
which one you meant to keep::

    Ld1S.fna exists and is not a symlink

Rename or remove the conflicting file, or pass ``--no-link`` to skip symlink
creation for that command.

``TriTrypDB needs a login``
----------------------------------

TriTrypDB requires an account to download FASTA/GFF files, so leishref can't fetch
them automatically the way it does for NCBI or Zenodo. ``leishref install`` on a
TriTrypDB catalog entry prints::

    TriTrypDB needs a login; get the file manually, then 'leishref dev add'

Download the files by hand from `tritrypdb.org <https://tritrypdb.org>`_, then add
them as a local assembly::

    leishref dev add TriTrypDB-68_LamazonensisPH8_Genome.fasta --alias LamPH8

Checksum mismatch after ``leishref verify``
-------------------------------------------------

::

    $ leishref verify
      mismatch: 1

    CHECKSUM MISMATCH:
      Ld1S: /home/you/.config/leishref/Ld1S/GCA_000227135.2_ASM22713v2_genomic.fna

The file on disk no longer matches the md5 recorded when it was installed —
typically because it was edited in place (``rename-sequences`` and
``prune-scaffold`` intentionally do this and update the stored checksum
themselves; anything else touching the file directly won't). Re-install to restore
the original::

    leishref install <name> --alias Ld1S --force

Duplicate catalog entries or aliases
------------------------------------------

``leishref dev check-aliases`` catches two classes of catalog corruption that are
otherwise easy to introduce by hand-editing ``metadata.yaml`` files or
``aliases.txt``: the same NCBI accession appearing under two catalog identifiers,
and the same shorthand alias pointing at two different accessions::

    leishref dev check-aliases

Run it after any manual catalog edit, and before opening a PR that touches
``leishref/data/``.

Catalog directories reorganized unexpectedly
--------------------------------------------------

The catalog's directory layout (``ncbi/``, ``scaffolds/``, ``custom/``,
``tritrypdb/``) is keyed strictly off each entry's ``source`` field, not off
whether it happens to have a Zenodo DOI or a particular file layout. A ``source:
Custom`` entry stays under ``custom/`` even after being published to Zenodo. If
you're scripting catalog changes, group by ``source`` and leave placement alone
otherwise — see :doc:`catalog` and the repository's ``CLAUDE.md`` for the full rule.

Symlinks have the wrong extension
----------------------------------------

All FASTA symlinks are standardized to ``.fna`` regardless of the underlying file's
extension (``.fa``, ``.fasta``, or already ``.fna``) — see
``leishref/links.py:link_name()``. This is intentional, not a bug: it gives
downstream tools one extension to expect no matter which archive a genome came
from. If a script depends on the *original* extension, read
``files.fasta`` from the genome's metadata (or ``leishref export``) rather than
the symlink name.
