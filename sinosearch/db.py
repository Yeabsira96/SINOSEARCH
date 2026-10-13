"""SQLite storage: documents, CJK-tokenized chunks (FTS5), vectors, crawl queue."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    domain      TEXT NOT NULL DEFAULT '',
    lang        TEXT NOT NULL DEFAULT 'zh',
    source_name TEXT NOT NULL DEFAULT '',   -- e.g. 知乎 / gov.cn
    published   TEXT NOT NULL DEFAULT '',    -- ISO date if known
    body        TEXT NOT NULL DEFAULT '',
    body_hash   TEXT NOT NULL DEFAULT '',
    crawled_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
    ord    INTEGER NOT NULL DEFAULT 0,
    text   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks(doc_id);

-- BM25 lane: we pre-tokenize (CJK -> space-separated unigrams+bigrams) because
-- FTS5's default tokenizer does not segment Chinese.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, chunk_id UNINDEXED
);

-- vector lane: stored as JSON floats; numpy does the cosine math.
CREATE TABLE IF NOT EXISTS chunk_vectors (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    vec      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_queue (
    url        TEXT PRIMARY KEY,
    domain     TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pending',  -- pending|done|failed|skipped
    hops       INTEGER NOT NULL DEFAULT 0,
    error      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cached English translations of Chinese chunk text (MT provider result or
-- offline gloss fallback) so we translate each snippet only once.
CREATE TABLE IF NOT EXISTS chunk_translations (
    chunk_id   INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    en         TEXT NOT NULL,
    provider   TEXT NOT NULL DEFAULT 'gloss',   -- gloss | openai | deepl ...
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Saved user searches: powers the "popular / trending" strip in the UI and
-- gives a hint of what people actually look up (research + casual mix).
CREATE TABLE IF NOT EXISTS search_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    q          TEXT NOT NULL,
    mode       TEXT NOT NULL DEFAULT 'search',  -- search | answer
    results    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA)


def insert_doc(conn: sqlite3.Connection, *, url: str, title: str, domain: str,
               lang: str, source_name: str, published: str, body: str,
               body_hash: str) -> int | None:
    """Insert or refresh a doc. Returns doc id, or None if unchanged."""
    row = conn.execute("SELECT id, body_hash FROM docs WHERE url = ?", (url,)).fetchone()
    if row and row["body_hash"] == body_hash:
        return None  # unchanged -> skip re-chunk/re-embed
    if row:
        conn.execute(
            """UPDATE docs SET title=?, domain=?, lang=?, source_name=?, published=?,
               body=?, body_hash=?, crawled_at=datetime('now') WHERE id=?""",
            (title, domain, lang, source_name, published, body, body_hash, row["id"]),
        )
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (row["id"],))
        doc_id = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO docs (url,title,domain,lang,source_name,published,body,body_hash)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (url, title, domain, lang, source_name, published, body, body_hash),
        )
        doc_id = cur.lastrowid
    return doc_id


def insert_chunks(conn: sqlite3.Connection, doc_id: int,
                  raw_texts: list[str]) -> list[int]:
    """Store ORIGINAL chunk text (for display). BM25 tokens live in chunks_fts
    — call fts_upsert() per chunk id after this."""
    ids: list[int] = []
    for ord_, txt in enumerate(raw_texts):
        cur = conn.execute(
            "INSERT INTO chunks (doc_id, ord, text) VALUES (?,?,?)",
            (doc_id, ord_, txt),
        )
        ids.append(cur.lastrowid)
    return ids


def fts_upsert(conn: sqlite3.Connection, chunk_id: int, tokenized: str) -> None:
    """Insert the CJK-tokenized form of a chunk into the BM25 lane."""
    conn.execute(
        "INSERT OR REPLACE INTO chunks_fts (rowid, content, chunk_id) VALUES (?,?,?)",
        (chunk_id, tokenized, chunk_id),
    )


def store_vector(conn: sqlite3.Connection, chunk_id: int, vec: list[float]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO chunk_vectors (chunk_id, vec) VALUES (?,?)",
        (chunk_id, json.dumps(vec)),
    )


def all_vectors(conn: sqlite3.Connection):
    for r in conn.execute("SELECT chunk_id, vec FROM chunk_vectors"):
        yield r["chunk_id"], json.loads(r["vec"])


def enqueue(conn: sqlite3.Connection, url: str, domain: str, hops: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO crawl_queue (url, domain, hops) VALUES (?,?,?)",
        (url, domain, hops),
    )


def next_pending(conn: sqlite3.Connection, limit: int = 10):
    return conn.execute(
        "SELECT url, domain, hops FROM crawl_queue WHERE status='pending'"
        " ORDER BY hops, rowid LIMIT ?",
        (limit,),
    ).fetchall()


def set_queue_status(conn: sqlite3.Connection, url: str, status: str,
                     error: str = "") -> None:
    conn.execute(
        "UPDATE crawl_queue SET status=?, error=?, updated_at=datetime('now')"
        " WHERE url=?",
        (status, error, url),
    )


def chunk_with_doc(conn: sqlite3.Connection, chunk_id: int):
    return conn.execute(
        """SELECT c.id AS chunk_id, c.text, c.ord, d.url, d.title, d.domain,
                  d.source_name, d.published
           FROM chunks c JOIN docs d ON d.id = c.doc_id WHERE c.id = ?""",
        (chunk_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# English-translation cache for chunks (bilingual result display).
# ---------------------------------------------------------------------------
def get_chunk_translation(conn: sqlite3.Connection, chunk_id: int) -> str | None:
    row = conn.execute(
        "SELECT en FROM chunk_translations WHERE chunk_id = ?", (chunk_id,)
    ).fetchone()
    return row["en"] if row else None


def put_chunk_translation(conn: sqlite3.Connection, chunk_id: int, en: str,
                          provider: str = "gloss") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO chunk_translations (chunk_id, en, provider) VALUES (?,?,?)",
        (chunk_id, en, provider),
    )


# ---------------------------------------------------------------------------
# Search log (powers trending queries in the UI).
# ---------------------------------------------------------------------------
def log_search(conn: sqlite3.Connection, q: str, mode: str, results: int) -> None:
    conn.execute(
        "INSERT INTO search_log (q, mode, results) VALUES (?,?,?)",
        (q.strip()[:200], mode, results),
    )


def popular_queries(conn: sqlite3.Connection, limit: int = 8):
    return conn.execute(
        """SELECT q, COUNT(*) c FROM search_log
           WHERE results > 0 AND created_at > datetime('now','-14 day')
           GROUP BY q ORDER BY c DESC LIMIT ?""",
        (limit,),
    ).fetchall()
