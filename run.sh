#!/usr/bin/env bash
# SinoSearch quickstart: build index from seed corpus, then launch the web app.
set -e
python -m sinosearch.seed_ingest
exec uvicorn sinosearch.server:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
