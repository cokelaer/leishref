"""Zenodo deposition management for scaffold publications."""

import json
import os
from pathlib import Path
from typing import Optional

import requests


class ZenodoError(Exception):
    pass


def get_zenodo_token(sandbox: bool = False) -> str:
    """Get Zenodo API token from env var.

    Production: ZENODO_TOKEN
    Sandbox: ZENODO_SANDBOX_TOKEN
    """
    var_name = "ZENODO_SANDBOX_TOKEN" if sandbox else "ZENODO_TOKEN"
    token = os.environ.get(var_name)
    if not token:
        raise ZenodoError(f"{var_name} env var not set")
    return token


def _headers(token: str) -> dict:
    """Return auth headers."""
    return {"Authorization": f"Bearer {token}"}


def create_deposition(title: str, description: str, creators: list[str], sandbox: bool = False) -> dict:
    """Create new Zenodo deposition. Returns deposition dict."""
    token = get_zenodo_token(sandbox=sandbox)
    base = "https://sandbox.zenodo.org" if sandbox else "https://zenodo.org"
    url = f"{base}/api/deposit/depositions"

    data = {
        "metadata": {
            "title": title,
            "description": description,
            "upload_type": "dataset",
            "creators": [{"name": c} for c in creators],
        }
    }

    r = requests.post(url, json=data, headers=_headers(token))
    if r.status_code not in [201, 200]:
        raise ZenodoError(f"Failed to create deposition: {r.status_code} {r.text}")

    return r.json()


def upload_file(deposition_id: int, fpath: Path, sandbox: bool = False) -> dict:
    """Upload file to deposition."""
    token = get_zenodo_token(sandbox=sandbox)
    fpath = Path(fpath)
    base = "https://sandbox.zenodo.org" if sandbox else "https://zenodo.org"

    # Get bucket URL from deposition
    dep_url = f"{base}/api/deposit/depositions/{deposition_id}"
    r = requests.get(dep_url, headers=_headers(token))
    if r.status_code != 200:
        raise ZenodoError(f"Failed to get deposition: {r.status_code}")

    bucket_url = r.json()["links"]["bucket"]

    # Upload file
    with open(fpath, "rb") as fp:
        r = requests.put(f"{bucket_url}/{fpath.name}", data=fp, headers=_headers(token))

    if r.status_code not in [200, 201]:
        raise ZenodoError(f"Failed to upload file: {r.status_code} {r.text}")

    return r.json()


def update_metadata(deposition_id: int, data: dict, sandbox: bool = False) -> dict:
    """Update deposition metadata."""
    token = get_zenodo_token(sandbox=sandbox)
    base = "https://sandbox.zenodo.org" if sandbox else "https://zenodo.org"
    url = f"{base}/api/deposit/depositions/{deposition_id}"

    r = requests.put(url, json=data, headers=_headers(token))
    if r.status_code != 200:
        raise ZenodoError(f"Failed to update metadata: {r.status_code} {r.text}")

    return r.json()


def publish_deposition(deposition_id: int, sandbox: bool = False) -> dict:
    """Publish deposition (makes it public)."""
    token = get_zenodo_token(sandbox=sandbox)
    base = "https://sandbox.zenodo.org" if sandbox else "https://zenodo.org"
    url = f"{base}/api/deposit/depositions/{deposition_id}/actions/publish"

    r = requests.post(url, headers=_headers(token))
    if r.status_code not in [202, 200]:
        raise ZenodoError(f"Failed to publish deposition: {r.status_code} {r.text}")

    return r.json()
