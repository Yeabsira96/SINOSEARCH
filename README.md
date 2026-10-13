# SinoSearch — China-native answers, in English

**The problem:** Foreigners (expats, investors, researchers, journalists, e-commerce sellers)
can't access or read the Chinese internet. The data they need lives on Zhihu, Baidu, Weibo,
Xiaohongshu, government portals, local news sites — behind a language wall and often behind
a geo/access wall. Google's index of China is shallow and stale.

**The product:** A search + answer engine that indexes **Chinese-native sources**, understands
queries asked in **English** (or any language), retrieves the right Chinese documents, and
returns an **English answer with citations back to the original Chinese sources**.

---

## Architecture (the "crawl → index → retrieve → answer" pipeline)

```
 User query (EN)                    Chinese web
      |                                  |
      v                                  v
 [1] QUERY TRANSLATE            [0] CRAWLER  (scrape CN sources, polite & incremental)
     EN -> ZH (+ keep EN)              |
      |                          [1'] NORMALIZE (clean HTML, dedupe, chunk, metadata)
      v                                  |
 [2] HYBRID SEARCH                 v
     BM25 (keyword)  +        [2'] INDEX  (SQLite FTS5 full-text + vector store)
     Vector (semantic)             |
      |                            v
      v                     [3] EMBED + STORE (multilingual embeddings:
 [3] RERANK/FUSE                text-2vec-multilingual / OpenAI fallback)
     (Reciprocal Rank Fusion)          ^
      |                                 |
      v                          (ingest-time)
 [4] SYNTHESIZE (RAG)
     LLM reads top-K Chinese chunks,
     writes English answer w/ [1][2][3] citations
      |
      v
 [5] API + WEB UI  (FastAPI + single-page UI)
```

### Why this approach (key decisions)

| Decision | Why |
|---|---|
| **Cross-lingual retrieval via translation at query time** (EN→ZH) rather than fine-tuning a model from scratch | Cheapest, highest-leverage. Multilingual embedders + MT give you 90% of the value on day one. Fine-tuning comes later, once you have query logs. |
| **Hybrid BM25 + vector search** | Chinese queries about names/products/policies are keyword-heavy ("公积金", "ICP备案"); semantic-only misses exact terms; keyword-only misses paraphrase. Fuse both (RRF). |
| **SQLite FTS5 + pluggable vector store** | Zero-ops start; migrate to Postgres+pgvector / Qdrant when corpus > ~1M docs. The interface (`index.py`) is swappable. |
| **LLM-agnostic synthesis (OpenAI API by default, any chat-completions-compatible endpoint)** | Don't train your own model. Your moat is the **corpus + ranking**, not the generator. |
| **Citations always point to original Chinese URL + translated snippet** | Trust is the product. Users can verify what was actually said in China. |

### Legal/ethical note (important for this space)
Scrape only public pages, respect robots.txt, rate-limit per domain, store source URLs,
and prefer official APIs (Weibo open API, gov data portals) where they exist. Some platforms
(XHS, Douyin) are effectively closed — plan partnerships/licensing for those later.

---

## Repo layout

```
sinosearch/
  config.py          # settings (env-driven)
  db.py              # SQLite schema: docs, chunks, crawl queue
  crawler.py         # polite incremental crawler for CN sources
  normalize.py       # HTML -> clean text, CJK-aware chunking, dedupe
  translate.py       # EN<->ZH machine translation (pluggable providers)
  embed.py           # multilingual embeddings (local HF or OpenAI)
  index.py           # hybrid search: FTS5 BM25 + vector cosine, RRF fusion
  answer.py          # RAG synthesis with citations
  server.py          # FastAPI app: /search, /answer, static UI
static/index.html    # minimal web UI
seed_data/*.html     # offline demo corpus (simulated scraped CN pages)
tests/test_pipeline.py
run.sh               # ingest seed data + launch server
```

## Quickstart

```bash
./run.sh                 # ingests seed corpus, starts API on :8000
# open http://localhost:8000  and try: "What do Chinese netizens think about EV subsidies?"
```

CLI without the server:

```bash
python -m sinosearch.seed_ingest            # build index from seed_data/
python -m sinosearch.cli "上海落户政策 2025"   # raw search
python -m sinosearch.cli --answer "How do I get a Shanghai hukou?"
```

## Roadmap (what we build next, in order)

1. **MVP (this repo):** pipeline end-to-end on a seed corpus — proves the UX loop.
2. **Real ingestion:** run `crawler.py` against a curated source list (Zhihu public pages,
   gov.cn policy portals, CNR/CGTN/SixthTone, 36kr, Huxiu, Baidu Zhidao mirrors).
3. **Better ranking:** cross-encoder reranker (e.g. `BAAI/bge-reranker-v2-m3`) +
   freshness/authority boosts per source.
4. **Verticals:** pick 1–2 wedges with paying users first — (a) market/consumer intel
   ("what are Chinese shoppers saying about X"), (b) expat/admin Q&A (visas, hukou, tax).
5. **Scale:** Postgres+pgvector or Qdrant, distributed crawl, incremental re-index.
6. **Moat building:** query-log-driven fine-tuned ranker + licensed exclusive sources.
