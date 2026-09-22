Development
============

Repository layout
------------------

::

    leishref/
      __init__.py
      cli.py           # Command-line interface
      metadata.py      # Genome metadata handling
      ncbi.py          # NCBI datasets integration
      agp.py           # AGP parsing and manipulation
      scaffold.py      # Ragtag scaffolding wrapper
      zenodo.py        # Zenodo publishing
      data/            # Shipped catalog (metadata.yaml per genome)

Contributing a genome
-----------------------

If you just want to add a genome to the catalog, you don't need to touch any code:
run ``leishref dev fetch-genome`` (an NCBI GCA/GCF assembly), ``leishref dev
fetch-nucleotide`` (a standalone NCBI nuccore record), or ``leishref dev add`` (a
local assembly), check the resulting ``leishref/data/.../metadata.yaml``, run
``leishref dev check-aliases`` to catch accidental duplicates, and open a pull
request with the new entry. See :doc:`workflow` for the full add → scaffold →
publish path, and :doc:`catalog` for where a new entry belongs.

Contributing code
--------------------

1. Fork the repository and create a branch for your change.
2. ``poetry install --with dev`` to set up a matching dev environment.
3. Make your change. Prefer small, focused commits over one large diff.
4. Add or update tests under ``tests/`` for any behavior change — see *Testing*
   below.
5. Run ``pre-commit run --all-files`` before committing; the same hooks run in CI,
   so a local pass avoids a red build.
6. Open a pull request describing *why* the change is needed, not just what
   changed — the diff already shows the what.

Code style is enforced by pre-commit hooks (black, isort, flake8; see
``.pre-commit-config.yaml`` and ``.flake8``) rather than by convention, so there's
nothing to memorize: run the hooks and fix whatever they flag.

Testing
-------

Run the test suite::

    poetry install --with dev
    pytest

With coverage::

    pytest --cov=leishref --cov-report=term-missing

A single test::

    pytest tests/test_cli.py::test_bundle_from_symlinks -xvs

Tests that would otherwise hit the network (NCBI, Zenodo) mock the relevant
function with ``monkeypatch`` rather than making real requests — see
``test_install_many_parallel_installs_all_genomes`` in ``tests/test_cli.py`` for
the pattern. Keep new tests network-free the same way, so the suite stays fast and
doesn't flake on connectivity.

Maintainer commands
-------------------

Add NCBI genome assembly to catalog::

    leishref dev fetch-genome GCA_000227135.2

Downloads metadata and FASTA/GFF from NCBI, creates ``leishref/data/ncbi/GCA_000227135.2/metadata.yaml``.

Add local assembly to catalog::

    leishref dev add ~/my_assembly.fasta \
        --alias Ltropica.CDC216-162.genome.flye --technology pacbio

``--alias`` is required: it becomes both the catalog identifier and the local
install name (unlike ``install``, where those two are separate). Adds the FASTA to
``leishref/data/local/`` with metadata, and installs it locally in the same step.
See :doc:`workflow` for the ``<species>.<strain>.<molecule_type>.<assembler>``
naming convention this alias follows.

Scaffold assembly against reference::

    leishref dev scaffold --query query.fasta --reference Ld1S

Creates scaffolded assembly by aligning query to reference, adds to ``leishref/data/scaffolds/``.

Publish a local genome to Zenodo::

    leishref dev publish Ltropica.CDC216-162.genome.flye

Takes the genome's local/catalog identifier - not a file path - since it uploads
whatever ``leishref install``-style install already produced for that name.
Uploads its files to Zenodo and records the DOI in catalog metadata. See
:doc:`workflow` for the full add → publish walk-through, including
``--confirm``/dry-run and the sandbox.
