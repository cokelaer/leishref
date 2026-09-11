"""Zenodo deposition management for scaffold publications."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


class ZenodoError(Exception):
    pass


def get_zenodo_token() -> str:
    """Get Zenodo API token from ZENODO_TOKEN env var."""
    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        raise ZenodoError("ZENODO_TOKEN env var not set")
    return token


def create_deposition(title: str, description: str, creators: list[str]) -> dict:
    """Create new Zenodo deposition. Returns deposition dict with 'id' and 'links'."""
    token = get_zenodo_token()
    headers = {"Content-Type": "application/json"}
    data = {
        "metadata": {
            "title": title,
            "description": description,
            "upload_type": "dataset",
            "creators": [{"name": c} for c in creators],
        }
    }

    cmd = [
        "curl",
        "-X",
        "POST",
        "https://zenodo.org/api/deposit/depositions",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(data),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ZenodoError(f"Failed to create deposition: {result.stderr}")

    deposition = json.loads(result.stdout)
    return deposition


def upload_file(deposition_id: int, fpath: Path) -> dict:
    """Upload file to deposition."""
    token = get_zenodo_token()
    fpath = Path(fpath)

    cmd = [
        "curl",
        "-X",
        "POST",
        f"https://zenodo.org/api/deposit/depositions/{deposition_id}/files",
        "-H",
        f"Authorization: Bearer {token}",
        "-F",
        f"file=@{fpath}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ZenodoError(f"Failed to upload file: {result.stderr}")

    file_data = json.loads(result.stdout)
    return file_data


def publish_deposition(deposition_id: int) -> dict:
    """Publish deposition (makes it public)."""
    token = get_zenodo_token()

    cmd = [
        "curl",
        "-X",
        "POST",
        f"https://zenodo.org/api/deposit/depositions/{deposition_id}/actions/publish",
        "-H",
        f"Authorization: Bearer {token}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ZenodoError(f"Failed to publish deposition: {result.stderr}")

    deposition = json.loads(result.stdout)
    return deposition
