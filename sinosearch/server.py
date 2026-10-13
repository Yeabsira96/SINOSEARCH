"""FastAPI app: /search, /answer, /stats, /ingest-url + single-page UI."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .answer import answer_query
from .config import settings
from .db import init_db, tx
from .index import hybrid_search
from .ingest import ingest_html
from .translate import translate

app = FastAPI(title="SinoSearch", version="0.1.0",
              description="China-native search & answers for English speakers.")


class SearchReq(BaseModel):
    query: str
    k: int | None = None


class AnswerReq(BaseModel):
    query: str
    k: int | None = None


class IngestUrlReq(BaseModel):
    url: str
    source_name: str = ""


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/stats")
def stats():
    init_db()
    with tx() as conn:
        docs = conn.execute("SELECT COUNT(*) c FROM docs").fetchone()["c"]
        chunks = conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
        by_src = conn.execute(
            "SELECT COALESCE(NULLIF(source_name,''), domain) name, COUNT(*) c"
            " FROM docs GROUP BY 1 ORDER BY c DESC LIMIT 20").fetchall()
    return {
        "docs": docs, "chunks": chunks,
        "sources": [{"name": r["name"], "docs": r["c"]} for r in by_src],
        "providers": {
            "embed": settings.embed_provider,
            "translate": settings.translate_provider,
            "llm": settings.llm_provider,
        },
    }


@app.post("/api/search")
def search(req: SearchReq):
    q = req.query.strip()
    if not q:
        raise HTTPException(400, "empty query")
    q_zh = translate(q, "zh")
    hits = hybrid_search(q_zh, final_k=req.k)
    return {
        "query": q,
        "query_zh": q_zh,
        "results": [{
            "n": i, "title": h.title, "url": h.url, "domain": h.domain,
            "source": h.source_name, "published": h.published,
            "snippet_zh": h.text[:300], "score": round(h.score, 5), "lane": h.lane,
        } for i, h in enumerate(hits, 1)],
    }


@app.post("/api/answer")
def answer(req: AnswerReq):
    q = req.query.strip()
    if not q:
        raise HTTPException(400, "empty query")
    a = answer_query(q, top_k=req.k)
    return {
        "query": a.query, "query_zh": a.query_zh, "answer": a.text,
        "mode": a.mode, "citations": a.citations,
    }


@app.post("/api/ingest-url")
def ingest_url(req: IngestUrlReq):
    """On-demand single-page ingestion (respects nothing here beyond size — use sparingly)."""
    import requests
    from .config import settings as st
    try:
        r = requests.get(req.url, timeout=15,
                         headers={"User-Agent": st.user_agent})
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"fetch failed: {e}")
    n = ingest_html(req.url, r.text, source_name=req.source_name)
    return {"url": req.url, "chunks_indexed": n}


_static = os.path.abspath(settings.static_dir)


@app.get("/")
def home():
    idx = os.path.join(_static, "index.html")
    if not os.path.exists(idx):
        return JSONResponse({"service": "SinoSearch", "ui": "static/index.html missing",
                             "endpoints": ["/api/search", "/api/answer", "/api/stats"]})
    return FileResponse(idx)
