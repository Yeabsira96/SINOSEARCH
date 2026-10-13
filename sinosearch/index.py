"""Hybrid retrieval: BM25 (FTS5) lane + vector cosine lane, fused with Reciprocal Rank Fusion.

Both lanes run over the *Chinese* query text (EN queries are translated upstream in
answer/server), which is what makes cross-lingual search work without a giant model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .config import settings
from .db import tx
from .embed import embed_texts
from .normalize import tokenize, query_terms


def _term_expansions(term: str) -> list[str]:
    """Query-side expansions for one token so BM25 matches indexed forms.

    ASCII words match as-is; CJK multi-char terms also match via their component
    unigrams/bigrams (e.g. 落户 hits the indexed bigram 落户 and chars 落/户).
    """
    toks = tokenize(term).split()
    return list(dict.fromkeys([term.lower(), *toks])) or [term]


def _is_cjk_term(term: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in term)


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    url: str
    title: str
    domain: str
    source_name: str
    published: str
    text: str          # original Chinese chunk text
    score: float       # fused RRF score
    lane: str          # "both" | "bm25" | "vector"


def _ascii_stopword(term: str) -> bool:
    t = term.lower()
    return t in {
        "what", "how", "who", "when", "where", "why", "does", "did", "do", "can",
        "could", "the", "a", "an", "and", "or", "for", "are", "is", "was", "were",
        "with", "about", "think", "know", "get", "want", "wanna", "need", "like",
        "make", "made", "many", "much", "some", "any", "all", "from", "into",
        "that", "this", "these", "those", "there", "they", "them", "their", "then",
        "than", "have", "has", "had", "will", "would", "should", "been", "being",
        "it", "its", "of", "to", "in", "on", "at", "by", "as", "be", "but", "not",
        "me", "my", "we", "you", "he", "she", "i",
        "china", "chinese",  # corpus is China-only: no discriminating signal
    }


def bm25_search(query_zh: str, k: int) -> list[tuple[int, float]]:
    """FTS5 BM25 over pre-tokenized chunks. Returns [(chunk_id, bm25_score)] best-first."""
    terms = query_terms(query_zh)
    if not terms:
        return []
    # Content-word filter: English stopwords carry no signal against a Chinese
    # corpus; CJK unigrams are too ambiguous to require on their own.
    allc = [q for q in dict.fromkeys(terms)
            if len(q) >= 2 and not (q.isascii() and _ascii_stopword(q))]
    cjk = [q for q in allc if _is_cjk_term(q)]
    latin = [q for q in allc if not _is_cjk_term(q)]
    # MUST = translated Chinese terms (reliable); SHOULD = romanized/English
    # leftovers like "hukou"/"shanghai", which usually aren't indexed verbatim.
    groups = ["(" + " OR ".join(f'"{t}"' for t in _term_expansions(q)) + ")"
              for q in cjk[:32]]
    should = ["(" + " OR ".join(f'"{t}"' for t in _term_expansions(q)) + ")"
              for q in latin[:16]]
    if not groups and should:
        groups = should
        should = []
    if not groups:
        # nothing but stopwords/unigrams -> fall back to OR of all tokens
        or_all = " OR ".join(f'"{t}"' for t in terms[:64])
        groups = [f"({or_all})"] if or_all else []
    if not groups:
        return []
    match = " AND ".join(groups)
    if should:
        # latin leftovers are a bonus signal, not a requirement (FTS5 NEAR syntax)
        match += " AND NEAR/" + str(len(should) + 8) + " " + " ".join(should)
    with tx() as conn:
        rows = conn.execute(
            """SELECT chunk_id, bm25(chunks_fts) AS s
               FROM chunks_fts WHERE chunks_fts MATCH ?
               ORDER BY s LIMIT ?""",
            (match, k),
        ).fetchall()
    # bm25() returns negative-is-better; flip to positive-is-better.
    return [(r["chunk_id"], -float(r["s"])) for r in rows]


def vector_search(query_zh: str, k: int) -> list[tuple[int, float]]:
    """Brute-force cosine over stored vectors. Fine to ~1M chunks; swap for ANN later."""
    with tx() as conn:
        rows = conn.execute("SELECT chunk_id, vec FROM chunk_vectors").fetchall()
    if not rows:
        return []
    ids = [r["chunk_id"] for r in rows]
    mat = np.asarray([json.loads(r["vec"]) for r in rows], dtype=np.float32)
    qv = np.asarray(embed_texts([query_zh])[0], dtype=np.float32)
    sims = mat @ qv  # vectors stored normalized -> dot == cosine
    top = np.argsort(-sims)[:k]
    return [(ids[i], float(sims[i])) for i in top]


def rrf_fuse(lanes: list[list[tuple[int, float]]], k_rrf: int) -> dict[int, float]:
    """Reciprocal Rank Fusion: score(d) = sum_lane 1/(k + rank)."""
    fused: dict[int, float] = {}
    for ranked in lanes:
        for rank, (cid, _s) in enumerate(ranked):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k_rrf + rank + 1)
    return fused


def hybrid_search(query_zh: str, final_k: int | None = None) -> list[Hit]:
    """Run both lanes on the Chinese query, fuse, hydrate docs, return ranked hits."""
    final_k = final_k or settings.final_top_k
    lane_k = settings.top_k_per_lane
    b = bm25_search(query_zh, lane_k)
    v = vector_search(query_zh, lane_k)
    fused = rrf_fuse([b, v], settings.rrf_k)
    if not fused:
        return []
    bids = {cid for cid, _ in b}
    vids = {cid for cid, _ in v}
    ordered = sorted(fused.items(), key=lambda kv: -kv[1])[:final_k]
    ids = [cid for cid, _ in ordered]
    placeholders = ",".join("?" * len(ids))
    with tx() as conn:
        rows = conn.execute(
            f"""SELECT c.id AS chunk_id, c.doc_id, c.text, d.url, d.title,
                       d.domain, d.source_name, d.published
                FROM chunks c JOIN docs d ON d.id = c.doc_id
                WHERE c.id IN ({placeholders})""",
            ids,
        ).fetchall()
    by_cid = {r["chunk_id"]: r for r in rows}
    hits: list[Hit] = []
    for cid, score in ordered:
        r = by_cid.get(cid)
        if r is None:
            continue
        lane = "both" if cid in bids and cid in vids else ("bm25" if cid in bids else "vector")
        hits.append(Hit(
            chunk_id=cid, doc_id=r["doc_id"], url=r["url"], title=r["title"],
            domain=r["domain"], source_name=r["source_name"], published=r["published"],
            text=r["text"], score=score, lane=lane,
        ))
    return hits
