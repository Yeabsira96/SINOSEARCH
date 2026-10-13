"""Seed ingestion: load the offline demo corpus (seed_data/*.html) into the index.

python -m sinosearch.seed_ingest [dir]
"""
from __future__ import annotations

import glob
import json
import os
import sys

from .config import settings
from .db import init_db
from .ingest import ingest_html


def _meta_for(path: str) -> dict:
    """Optional sidecar metadata: foo.html + foo.meta.json {url,source,published}."""
    meta_path = os.path.splitext(path)[0] + ".meta.json"
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def ingest_one_path(path: str) -> int:
    """Ingest a local HTML file (or file:// URL) with optional sidecar metadata."""
    if path.startswith("file://"):
        path = path[len("file://"):]
    with open(path, encoding="utf-8") as f:
        html = f.read()
    meta = _meta_for(path)
    url = meta.get("url") or f"file://{os.path.abspath(path)}"
    return ingest_html(
        url, html,
        source_name=meta.get("source_name", ""),
        published=meta.get("published", ""),
    )


def ingest_directory(directory: str) -> int:
    total = 0
    files = sorted(glob.glob(os.path.join(directory, "*.html")))
    if not files:
        print(f"no *.html found under {directory}", file=sys.stderr)
    for p in files:
        n = ingest_one_path(p)
        print(f"  {os.path.basename(p)}: {n} chunks")
        total += n
    return total


def main() -> int:
    init_db()
    d = sys.argv[1] if len(sys.argv) > 1 else settings.seed_dir
    n = ingest_directory(d)
    print(f"done: {n} chunks indexed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
