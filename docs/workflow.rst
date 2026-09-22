Workflow Examples
==================

End-to-end walk-throughs that chain several commands together. Each section stands
alone; skip ahead to the one that matches what you're doing.

Using the shipped catalog
--------------------------

The common case: find a genome, install it, and confirm it's intact.

::

    # See what's available
    leishref search donovani

    # Install it under a short local alias
    leishref install GCA_000227135.2 --alias Ld1S

    # Confirm the checksum matches what the catalog recorded
    leishref verify

``leishref install`` creates ``~/.config/leishref/Ld1S/`` with the FASTA (and GFF, if
the catalog entry has one) plus an absolute symlink ``Ld1S.fna`` in the current
directory, and appends the install to ``./accessions.txt`` so it can be replayed
later with ``leishref restore``.

Rebuilding a database on a new machine
----------------------------------------

``accessions.txt`` is the portable record of what a project needs. Commit it
alongside your analysis code instead of the downloaded genomes themselves::

    # On the original machine, after installing everything the project needs
    git add accessions.txt

    # On a new machine (or after clearing ~/.config/leishref)
    git clone <project-repo>
    cd <project-repo>
    leishref restore

    # Faster, for a large accessions.txt
    leishref restore --parallel 8

    # See what would happen first
    leishref restore --dry-run

``restore`` skips genomes that are already installed with a matching checksum, so
re-running it after a partial failure only fetches what's still missing.

Adding a genome and deriving a scaffold
------------------------------------------

The full maintainer path for adding a new assembly to the catalog and building a
scaffold from it, from raw FASTA through to a published, installable entry.

::

    # 1. Add a local assembly (e.g. from your own sequencing run)
    leishref dev add my_assembly.fasta --alias Ltrop.raw --species "Leishmania tropica"

    # 2. Scaffold it against an existing reference in the catalog
    leishref dev scaffold --query Ltrop.raw --reference Ld1S --clean

    # This prints the auto-generated name, e.g. Ltrop.raw.scaffold.Ld1S, and installs
    # the result locally exactly like `leishref install` would.

    # 3. Inspect what was produced
    leishref info Ltrop.raw.scaffold.Ld1S
    leishref verify

    # 4. Publish the scaffold to Zenodo once you're happy with it
    leishref dev publish Ltrop.raw.scaffold.Ld1S            # dry-run: shows what would upload
    leishref dev publish Ltrop.raw.scaffold.Ld1S --confirm --version v1.0

    # Publishing records the DOI in leishref/data/, so the entry now installs via
    # Zenodo for everyone else too:
    leishref install Ltrop.raw.scaffold.Ld1S --alias my-scaffold

Adding a local file to the database and publishing it to Zenodo
---------------------------------------------------------------------

The direct path, for a genome you already have as a FASTA - not derived by
scaffolding anything (see the previous section if it is). Typical for a genome you
assembled yourself, or downloaded from somewhere leishref doesn't fetch from
automatically (e.g. TriTrypDB, which needs a login).

``dev add`` only *stages* a genome for review; it doesn't touch the shipped catalog
or your local install. ``dev publish`` is the step that actually deposits it on
Zenodo and adds it to ``leishref/data/custom/``.

Naming convention
^^^^^^^^^^^^^^^^^^^

The staged entry is named after the FASTA file itself, so name the file before
running ``dev add``::

    <species>.<strain>.<molecule_type>.<assembler>

e.g. ``Ltropica.CDC216-162.maxicircle.flye.fasta``. ``<assembler>`` is optional -
drop it (and the trailing dot) if unknown or not meaningful, e.g. for a genome
downloaded rather than assembled locally. ``<molecule_type>`` is one of:

- ``genome`` -- whole nuclear genome, unassigned to chromosomes
- ``chromosome`` -- chromosome-level nuclear assembly
- ``scaffold`` -- nuclear assembly below chromosome level (contigs/scaffolds only)
- ``maxicircle`` -- kinetoplast maxicircle
- ``minicircle`` -- kinetoplast minicircle

This is the *filename* convention (readable at a glance, sorts sensibly next to
related entries); it's separate from the ``--molecule-type`` metadata field below,
which tags a *kinetoplast* entry specifically (``kinetoplast,maxicircle`` or
``kinetoplast,minicircle`` -- see :doc:`metadata`) so it turns up in
``leishref search kinetoplast``. An ordinary nuclear genome or chromosome needs no
``--molecule-type`` at all.

::

    # 1. Stage it for review - writes to ./to_publish_on_zenodo/<fasta-stem>/,
    #    nowhere else. --alias here is just a note in metadata.yaml, e.g. what you
    #    called it in your own notes; it plays no structural role.
    leishref dev add Ltropica.CDC216-162.genome.flye.fasta \
        --species "Leishmania tropica" --strain "CDC216-162" \
        --technology "PacBio RS II" --assembler Flye

    # A GFF, if you have one, goes right after the FASTA:
    leishref dev add Ltropica.CDC216-162.genome.flye.fasta assembly.gff

    # A standalone kinetoplast/maxicircle instead of a nuclear genome? Tag it so
    # it's searchable (see :doc:`metadata`):
    leishref dev add Ltropica.CDC216-162.maxicircle.flye.fasta \
        --molecule-type kinetoplast,maxicircle

    # 2. Review what was staged
    cat to_publish_on_zenodo/Ltropica.CDC216-162.genome.flye/metadata.yaml

    # 3. Set your Zenodo token (production or sandbox)
    export ZENODO_TOKEN=your-token                    # zenodo.org
    export ZENODO_SANDBOX_TOKEN=your-sandbox-token     # sandbox.zenodo.org, with --sandbox

    # 4. Publish - dry-run first, shows what would upload without touching Zenodo
    leishref dev publish to_publish_on_zenodo/Ltropica.CDC216-162.genome.flye
    leishref dev publish to_publish_on_zenodo/Ltropica.CDC216-162.genome.flye \
        --confirm --version v1.0

    # Rehearse on the sandbox first if you're not sure: a sandbox DOI is deliberately
    # not recorded in the catalog, so it can't block the real publish afterwards.
    leishref dev publish to_publish_on_zenodo/Ltropica.CDC216-162.genome.flye \
        --confirm --sandbox

``dev publish`` takes a path to the staged directory (not the ``--alias``, and not a
file path to the FASTA itself). Once published, a fresh entry appears under
``leishref/data/custom/`` with the DOI recorded and ``source: Custom`` unchanged
(staying in ``custom/`` per :doc:`catalog`'s placement rule, even though it now has
a DOI) - so from then on
``leishref install Ltropica.CDC216-162.genome.flye --alias <anything>`` fetches it
from Zenodo instead of needing your local file again, including for anyone else who
pulls the catalog update. Commit that ``metadata.yaml`` (only metadata - never the
sequence itself, which stays out of source control) as a pull request; see
:doc:`development`.

The staged copy under ``to_publish_on_zenodo/`` is left in place afterwards (also
updated with the DOI, for reference) - remove it yourself once you've confirmed the
catalog entry looks right.

Packaging genomes for offline sharing
----------------------------------------

Two ways to get files out of leishref and into a single archive, depending on
whether you're starting from symlinks in your working directory or from database
aliases directly::

    # From the alias-named symlinks already sitting in your project directory
    ls
    # Ld1S.fna  LdBPK.fna  notebook.ipynb
    leishref bundle '*.fna' -o genomes.tar.gz

    # Directly by alias, no symlinks required
    leishref bundle Ld1S LdBPK -o genomes.tar.gz
    leishref bundle 'Ld*' -o all-ld-strains.tar.gz

Both resolve to the real files under ``~/.config/leishref`` — the archive never
contains a bare symlink, even though your working directory only ever shows one.

Exporting the catalog for downstream analysis
-------------------------------------------------

``export`` is the machine-readable counterpart to ``info``, for feeding a paper's
supplementary table or a notebook::

    # Everything in the shipped catalog, one row per genome
    leishref export --format tsv -o supplementary_table.tsv

    # Catalog and your local installs together, as JSON for a script
    leishref export --source both --format json | jq '.[] | .identifier'

    # YAML, if you want to hand-edit or diff it
    leishref export --format yaml -o catalog_snapshot.yaml

See :doc:`metadata` for what each field means.
