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
    ap.add_argument("--crawl", action="store_true",
                    help="run the polite crawler against the curated source registry")
    ap.add_argument("--category", action="append", default=[],
                    help="limit crawl to categories (gov|business|ecommerce|social|news); repeatable")
    ap.add_argument("--source", action="append", default=[],
                    help="limit crawl to named sources/domains; repeatable")
    ap.add_argument("--max-pages", type=int, default=50, help="crawl page budget")
    ap.add_argument("--max-hops", type=int, default=2, help="crawl depth from each seed")
    ap.add_argument("--list-sources", action="store_true", help="print the source registry and exit")
    args = ap.parse_args(argv)

    init_db()

    if args.list_sources:
        from .sources import REGISTRY
        for s in REGISTRY:
            print(f"[{s.category:<9}] {s.name} ({s.domain})\n            {s.notes}")
        return 0

    if args.crawl:
        from .crawler import Crawler
        from .sources import sources_for, seed_pairs, display_map
        srcs = sources_for(categories=args.category or None,
                           names=args.source or None)
        if not srcs:
            print("no sources matched --category/--source", file=sys.stderr)
            return 1
        allowed = [s.domain for s in srcs]
        cr = Crawler(max_pages=args.max_pages, max_hops=args.max_hops,
                     allowed_domains=allowed)
        n = cr.run(seeds=seed_pairs(srcs), display_sources=display_map(srcs))
        print(f"crawled+indexed {n} pages from {len(srcs)} sources")
        return 0

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
