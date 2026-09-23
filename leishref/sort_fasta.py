#!/usr/bin/env python3
"""Sort FASTA: chr 1-36, then maxicircle, then extra contigs by size desc."""
import sys

from Bio import SeqIO

infile, outfile = sys.argv[1], sys.argv[2]
records = list(SeqIO.parse(infile, "fasta"))

chroms = []
maxicircle = None
extras = []

for rec in records:
    name = rec.id
    if name.isdigit():
        chroms.append((int(name), rec))
    elif name.lower() == "maxicircle":
        maxicircle = rec
    else:
        extras.append(rec)

chroms.sort(key=lambda x: x[0])
extras.sort(key=lambda r: len(r.seq), reverse=True)

out = [rec for _, rec in chroms]
if maxicircle is not None:
    out.append(maxicircle)
for i, rec in enumerate(extras, start=1):
    rec.id = f"extra_contig_{i}"
    rec.description = ""
    rec.name = rec.id
out.extend(extras)

SeqIO.write(out, outfile, "fasta")
print(f"chroms={len(chroms)} maxicircle={'yes' if maxicircle else 'no'} extras={len(extras)}")
