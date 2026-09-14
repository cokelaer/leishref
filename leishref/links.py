"""Alias-named symlinks, created next to wherever leishref was run.

Data files keep the name their source gave them, which is rarely the name anyone wants
to type. A symlink named after the alias gives a stable, readable handle to pass to
other tools without copying or renaming anything.
"""

import os
from pathlib import Path
from typing import Optional


class LinkConflict(Exception):
    """A real file already occupies the link name."""


def link_name(alias: str, target: Path) -> str:
    """Alias plus the target's extension, so file-type sniffing still works."""
    return f"{alias}{Path(target).suffix}"


def make_link(alias: str, target: Path, basedir: Path = Path(".")) -> Optional[Path]:
    """Point <alias><ext> in basedir at target. Returns the link, or None if unchanged.

    The link is relative so the tree can be moved or shared without breaking. An existing
    symlink is replaced; an existing regular file is never overwritten.
    """
    target = Path(target)
    basedir = Path(basedir)
    link = basedir / link_name(alias, target)

    if link.exists() and not link.is_symlink():
        raise LinkConflict(f"{link} exists and is not a symlink")

    relative = os.path.relpath(target.resolve(), start=basedir.resolve())

    if link.is_symlink():
        if os.readlink(link) == relative:
            return None
        link.unlink()

    link.symlink_to(relative)
    return link


def link_paths(alias: str, paths, basedir: Path = Path(".")) -> list[Path]:
    """Link an explicit set of files, for callers that know where they just wrote."""
    made = []
    for path in paths:
        if path is None:
            continue
        link = make_link(alias, Path(path), basedir)
        if link is not None:
            made.append(link)
    return made
