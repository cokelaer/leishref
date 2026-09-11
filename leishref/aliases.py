"""User-maintained alias to filename/accession mapping."""

import csv
from pathlib import Path
from typing import Optional


class Aliases:
    """Load and resolve user aliases."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._cache = {}
        self._load()

    def _load(self) -> None:
        """Load aliases from CSV."""
        if not self.path.exists():
            return
        with open(self.path, "r") as f:
            reader = csv.DictReader(f, fieldnames=["alias", "target"])
            for row in reader:
                if row.get("alias") and row.get("target"):
                    self._cache[row["alias"]] = row["target"]

    def resolve(self, alias_or_path: str) -> Optional[str]:
        """Resolve alias to target (accession or filename). Return as-is if not found."""
        self._load()  # re-read in case changed
        if alias_or_path in self._cache:
            return self._cache[alias_or_path]
        return alias_or_path

    def add(self, alias: str, target: str) -> None:
        """Add or update alias."""
        self._cache[alias] = target
        self._write()

    def _write(self) -> None:
        """Write aliases to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["alias", "target"])
            writer.writeheader()
            for alias, target in sorted(self._cache.items()):
                writer.writerow({"alias": alias, "target": target})

    def __getitem__(self, alias: str) -> str:
        """Shorthand: aliases[alias]."""
        return self._cache[alias]

    def __contains__(self, alias: str) -> bool:
        """Check if alias exists."""
        return alias in self._cache
