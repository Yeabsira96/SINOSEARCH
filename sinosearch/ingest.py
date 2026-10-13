"""Ingestion: turn raw scraped pages into indexed, embedded chunks."""
from __future__ import annotations

from .config import settings
from .db import init_db, tx, insert_doc, insert_chunks, fts_upsert, store_vector
from .embed import embed_texts
from .normalize import html_to_text, tokenize, chunk_text, body_hash


def ingest_html(url: str, html: str, *, source_name: str = "",
                published: str = "", lang: str = "zh", domain: str = "") -> int:
    """Normalize -> chunk -> FTS index -> embed. Returns #chunks added (0 if doc unchanged).

    Storage split (see db.insert_chunks): the `chunks` table keeps the ORIGINAL text
    (for display/snippets); `chunks_fts` keeps the CJK-tokenized form (for BM25).
    """
    title, text = html_to_text(html)
    if not text.strip():
        return 0
    if not domain:
        domain = url.split("/")[2] if "://" in url else ""
    h = body_hash(text)
    with tx() as conn:
        doc_id = insert_doc(
            conn, url=url, title=title, domain=domain, lang=lang,
            source_name=source_name, published=published, body=text, body_hash=h,
        )
        if doc_id is None:
            return 0
        raw_chunks = chunk_text(text)
        ids = insert_chunks(conn, doc_id, raw_chunks)
        for cid, tok in zip(ids, (tokenize(c) for c in raw_chunks)):
            fts_upsert(conn, cid, tok)
        vecs = embed_texts(raw_chunks)
        for cid, v in zip(ids, vecs):
            store_vector(conn, cid, v)
        return len(ids)


def reindex_all() -> int:
    """Re-embed/re-tokenize every stored doc body (e.g., after changing providers)."""
    total = 0
    with tx() as conn:
        rows = conn.execute("SELECT id, body FROM docs").fetchall()
    for r in rows:
        raw_chunks = chunk_text(r["body"])
        with tx() as conn:
            conn.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN"
                " (SELECT id FROM chunks WHERE doc_id=?)", (r["id"],))
            conn.execute("DELETE FROM chunks WHERE doc_id=?", (r["id"],))
            ids = insert_chunks(conn, r["id"], raw_chunks)
            for cid, tok in zip(ids, (tokenize(c) for c in raw_chunks)):
                fts_upsert(conn, cid, tok)
            vecs = embed_texts(raw_chunks)
            for cid, v in zip(ids, vecs):
                store_vector(conn, cid, v)
            total += len(ids)
    return total
