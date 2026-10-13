"""CLI: python -m sinosearch.cli [--answer|--ingest-dir DIR|--add-url PATH] "query"
"""
from __future__ import annotations

import argparse
import sys

from .db import init_db


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sinosearch", description="SinoSearch CLI")
    ap.add_argument("query", nargs="?", default="", help="question or search terms")
    ap.add_argument("--answer", action="store_true", help="RAG answer mode (else raw search)")
    ap.add_argument("--k", type=int, default=None, help="number of results/chunks")
    ap.add_argument("--ingest-dir", metavar="DIR", help="ingest an HTML directory and exit")
    ap.add_argument("--add-url", metavar="URL", help="ingest one local file:// or html path and exit")
    args = ap.parse_args(argv)

    init_db()

    if args.ingest_dir:
        from .seed_ingest import ingest_directory
        n = ingest_directory(args.ingest_dir)
        print(f"indexed {n} chunks from {args.ingest_dir}")
        return 0

    if args.add_url:
        from .seed_ingest import ingest_one_path
        n = ingest_one_path(args.add_url)
        print(f"indexed {n} chunks from {args.add_url}")
        return 0

    if not args.query:
        ap.print_help()
        return 1

    if args.answer:
        from .answer import answer_query
        a = answer_query(args.query, top_k=args.k)
        print(f"QUERY      : {a.query}")
        print(f"ZH QUERY   : {a.query_zh}")
        print(f"MODE       : {a.mode}\n")
        print(a.text)
        print("\nCITATIONS:")
        for c in a.citations:
            print(f"  [{c['n']}] {c['source'] or c['domain']} — {c['title']}\n      {c['url']}")
    else:
        from .translate import translate
        from .index import hybrid_search
        q_zh = translate(args.query, "zh")
        print(f"ZH QUERY: {q_zh}\n")
        for i, h in enumerate(hybrid_search(q_zh, final_k=args.k), 1):
            print(f"[{i}] ({h.lane}, {h.score:.4f}) {h.source_name or h.domain} — {h.title}")
            print(f"    {h.text[:160]}")
            print(f"    {h.url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
