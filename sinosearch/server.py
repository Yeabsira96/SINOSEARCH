"""FastAPI app: GET / serves the UI; /api/search and /api/answer return JSON.

Modes (user asked to balance research vs casual):
  mode=search   — plain hybrid retrieval, fast, bilingual snippets (casual + research)
  mode=answer   — RAG synthesis with citations (deep research)
Extras merged into every response:
  * English meaning for every Chinese result (bilingual.decorate — MT if configured,
    offline dictionary gloss otherwise)
  * Baidu discovery lane when LIVE=1 (web.enrich_with_baidu; graceful on bot-wall)
  * Social-platform deep links (Weibo/Zhihu/RED/Bilibili/Douyin/Tieba)
  * Trending strip from locally logged searches (search_log table)
Run: uvicorn sinosearch.server:app --port 8090
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from . import web
from .answer import answer_query
from .bilingual import decorate
from .config import settings
from .db import init_db, tx, log_search, popular_queries
from .index import hybrid_search
from .translate import translate

app = FastAPI(title="SinoSearch", version="0.2.0")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _trending():
    try:
        with tx() as conn:
            return popular_queries(conn, 8)
    except Exception:
        return []


def _common_payload(q: str, mode: str) -> dict:
    """Bilingual query info + social links + trending, shared by both endpoints."""
    q = q.strip()
    query_zh = translate(q, "zh") if q else q
    is_en = not any("\u4e00" <= c <= "\u9fff" for c in q)
    return {
        "q": q,
        "query_zh": query_zh if query_zh != q else "",
        "translated": is_en and query_zh != q,
        "mode": mode,
        "live": bool(int(os.environ.get("LIVE", "0"))),
        "social_links": web.social_links(query_zh or q) if q else [],
        "trending": [{"q": r["q"], "c": r["c"]} for r in _trending()],
    }


@app.get("/api/search")
def api_search(q: str, top_k: int = 10, baidu: int = 0):
    q = q.strip()
    if not q:
        return JSONResponse({"error": "empty query"}, status_code=400)
    payload = _common_payload(q, "search")
    query_zh = payload["query_zh"] or q
    hits = hybrid_search(query_zh, final_k=top_k)
    results = decorate(hits)
    # merge Baidu discovery lane when requested AND LIVE=1
    baidu_info = {"attempted": False}
    if baidu and payload["live"]:
        baidu_info = web.enrich_with_baidu(query_zh, max_results=5, follow=False)
    try:
        with tx() as conn:
            log_search(conn, q, "search", len(results))
    except Exception:
        pass
    return {"results": results, "baidu": baidu_info, **payload}


@app.get("/api/answer")
def api_answer(q: str, top_k: int = 6, baidu: int = 0):
    q = q.strip()
    if not q:
        return JSONResponse({"error": "empty query"}, status_code=400)
    payload = _common_payload(q, "answer")
    if payload["live"] and baidu:
        web.enrich_with_baidu(payload["query_zh"] or q, max_results=5, follow=True)
    ans = answer_query(q, top_k=top_k)
    try:
        with tx() as conn:
            log_search(conn, q, "answer", len(ans.citations))
    except Exception:
        pass
    return {
        "text": ans.text,
        "answer_mode": ans.mode,
        "citations": ans.citations,      # already bilingual via answer.py
        **payload,
    }


@app.get("/api/status")
def api_status():
    with tx() as conn:
        counts = {r["k"]: r["c"] for r in conn.execute(
            """SELECT 'docs' k, COUNT(*) c FROM docs
               UNION ALL SELECT 'chunks', COUNT(*) FROM chunks""")}
    return {
        "llm_provider": settings.llm_provider,
        "embeddings_provider": settings.embed_provider,
        "translate_provider": settings.translate_provider,
        "live_crawl_enabled": bool(int(os.environ.get("LIVE", "0"))),
        "counts": counts,
        "sources": [d["source_name"] or d["domain"] for d in _source_list()],
    }


def _source_list(limit: int = 30):
    try:
        with tx() as conn:
            return conn.execute(
                """SELECT domain, source_name, COUNT(*) n FROM docs
                   GROUP BY domain ORDER BY n DESC LIMIT ?""", (limit,)
            ).fetchall()
    except Exception:
        return []
