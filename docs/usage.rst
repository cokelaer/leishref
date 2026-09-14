Usage
=====

Quick start
-----------

List the entire catalog::

    leishref info

Search for genomes::

    leishref search donovani

Download a genome locally::

    leishref download --alias Ld1S GCA_000227135.2

Verify checksums::

    leishref verify

User commands
-------------

.. code-block:: console

    $ leishref --help
    Usage: leishref [OPTIONS] COMMAND [ARGS]...

    User Commands:
      download    Install a catalog genome into the local database under ALIAS
      info        List the catalog and the local database
      search      Find catalog genomes matching every term
      verify      Check the local database against recorded checksums

    Developer Commands:
      dev         Commands for maintaining the shipped catalog

For full command details::

    leishref <command> --help
