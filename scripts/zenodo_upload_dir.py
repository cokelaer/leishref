"""Create a Zenodo deposition from a directory and upload its files.

Usage: ZENODO_TOKEN=... python scripts/zenodo_upload_dir.py upload/ [--sandbox] [--publish] [--deposition ID]

The directory must contain zenodo_metadata.json ({"metadata": {...}}); every other file is uploaded (symlinks are
followed). Without --publish the deposition is left as a draft to review on the Zenodo website.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import requests

from leishref.zenodo import _headers, create_deposition, get_zenodo_token, publish_deposition, update_metadata

p = argparse.ArgumentParser()
p.add_argument("directory", type=Path)
p.add_argument("--sandbox", action="store_true")
p.add_argument("--publish", action="store_true", help="publish (irreversible: issues a DOI)")
p.add_argument("--deposition", type=int, help="resume uploading to an existing draft")
p.add_argument("--dry-run", action="store_true")
args = p.parse_args()

meta = json.loads((args.directory / "zenodo_metadata.json").read_text())
files = sorted(f for f in args.directory.iterdir() if f.name != "zenodo_metadata.json" and f.is_file())
total = sum(f.stat().st_size for f in files)
print(f"{len(files)} files, {total / 1e9:.2f} GB, target: {'sandbox' if args.sandbox else 'PRODUCTION'} zenodo")
if args.dry_run:
    raise SystemExit(0)

m = meta["metadata"]
if args.deposition:
    dep_id = args.deposition
else:
    dep = create_deposition(m["title"], m["description"], [c["name"] for c in m["creators"]], sandbox=args.sandbox)
    dep_id = dep["id"]
print("deposition", dep_id)
update_metadata(dep_id, meta, sandbox=args.sandbox)
base = "https://sandbox.zenodo.org" if args.sandbox else "https://zenodo.org"
headers = _headers(get_zenodo_token(sandbox=args.sandbox))
info = requests.get(f"{base}/api/deposit/depositions/{dep_id}", headers=headers, timeout=60).json()
bucket = info["links"]["bucket"]
done = {f["filename"]: f["checksum"] for f in info.get("files", [])}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


for i, f in enumerate(files, 1):
    if done.get(f.name) == md5(f):
        print(f"[{i}/{len(files)}] {f.name} already uploaded, skipped", flush=True)
        continue
    for attempt in range(1, 6):
        t0 = time.time()
        try:
            with open(f, "rb") as fp:
                r = requests.put(f"{bucket}/{f.name}", data=fp, headers=headers, timeout=(30, 600))
            if r.status_code in (200, 201):
                break
            print(f"  {f.name}: HTTP {r.status_code} {r.text[:150]}", flush=True)
        except requests.RequestException as e:
            print(f"  {f.name}: attempt {attempt} failed ({type(e).__name__})", flush=True)
        time.sleep(10 * attempt)
    else:
        raise SystemExit(f"giving up on {f.name}; rerun with --deposition {dep_id}")
    print(f"[{i}/{len(files)}] {f.name} ({f.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f} s)", flush=True)
if args.publish:
    rec = publish_deposition(dep_id, sandbox=args.sandbox)
    print("published:", rec.get("doi"), rec["links"].get("html"))
else:
    print("draft ready, review and publish on the Zenodo website (or rerun with --deposition", dep_id, "--publish)")
