"""Dump the leishref catalog to catalog.json for the static search page.

Usage: python build_catalog.py [output.json]
"""
import json
import sys
from pathlib import Path

from leishref.metadata import catalog, catalog_group, load_aliases


def main(out="catalog.json"):
    by_acc = {}
    for alias, acc in load_aliases().items():
        by_acc.setdefault(acc, []).append(alias)
    rows = []
    for g in catalog():
        d = g.to_dict()
        d = {k: v for k, v in d.items() if v not in (None, "", {}, [])}
        d["group"] = catalog_group(g)
        d["aliases"] = sorted(set(by_acc.get(g.identifier, []) + by_acc.get(getattr(g, "accession", None) or "", [])))
        rows.append(d)
    Path(out).write_text(json.dumps(rows, default=str, separators=(",", ":")))
    print(f"{len(rows)} genomes -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
