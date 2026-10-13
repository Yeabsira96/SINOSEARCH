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
  db.py              # SQLite schema: docs, chunks, FTS5, vectors, crawl queue
  sources.py         # curated registry of top CN sites (gov/business/social/news/ecommerce)
  crawler.py         # polite incremental crawler (robots.txt, per-domain rate limit)
  normalize.py       # HTML -> clean text, CJK-aware chunking, dedupe
  translate.py       # EN<->ZH machine translation (pluggable providers + business glossary)
  embed.py           # multilingual embeddings (hash offline / local HF / OpenAI)
  index.py           # hybrid search: FTS5 BM25 + vector cosine, RRF fusion
  answer.py          # RAG synthesis with citations
  ingest.py          # html -> chunks -> fts -> vectors
  seed_ingest.py     # load seed_data/*.html demo corpus
  cli.py             # query / --answer / --crawl / --list-sources
  server.py          # FastAPI app: /api/search, /api/answer, /api/stats, static UI
static/index.html    # minimal web UI
seed_data/*.html     # offline demo corpus (simulated scraped CN pages)
tests/test_pipeline.py
run.sh               # ingest seed data + launch server
```

## Focus: market-expansion research

This build is tuned for **researchers and overseas businesses evaluating entry into the
China market**. Ask questions like:

- "What are the foreign investment negative list rules?"
- "How saturated is the coffee shop market in China?"
- "Which e-commerce platforms do foreign beauty brands use to enter China?"

`sources.py` curates the crawl targets across five categories:
`gov` (policy/regulators), `business` (36kr/Huxiu/Iyiou), `ecommerce` (Taobao/JD/PDD merchant
content), `social` (Zhihu/XHS/Weibo sentiment), `news` (state + financial portals).

## Quickstart

```bash
pip install -r requirements.txt
./run.sh                 # ingests seed corpus, starts API on :8000
# open http://localhost:8000  — try: "How can a foreign brand enter the Chinese market?"
```

CLI without the server:

```bash
python -m sinosearch.cli --list-sources            # show the curated CN site registry
python -m sinosearch.cli --crawl --category gov --max-pages 20   # live crawl (polite)
python -m sinosearch.cli "上海落户政策 2025"        # raw hybrid search
python -m sinosearch.cli --answer "shanghai hukou policy for foreigners"
python -m unittest discover -s tests               # run the pipeline test suite
```

### Running with real AI providers (optional but recommended)

The default config runs **fully offline** (hash embeddings + echo answers). To upgrade:

```bash
# Semantic search via OpenAI embeddings + real MT + synthesized English answers:
export SINO_EMBED_PROVIDER=openai
export SINO_TRANSLATE_PROVIDER=openai
export SINO_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
python -m sinosearch.ingest   # or re-run seed ingest; then reindex:
python -c "from sinosearch.ingest import reindex_all; reindex_all()"

# Or free/local semantic embeddings (needs ~1GB model download):
export SINO_EMBED_PROVIDER=hf
pip install sentence-transformers
```

Provider matrix (all env vars prefixed `SINO_`, see `config.py`):

| Env var | Offline default | Production options |
|---|---|---|
| `SINO_EMBED_PROVIDER` | `hash` | `hf` (text2vec-multilingual), `openai` |
| `SINO_TRANSLATE_PROVIDER` | `noop` (glossary) | `openai` |
| `SINO_LLM_PROVIDER` | `echo` (extractive) | `openai` |

## Publishing to GitHub

```bash
git init -b main && git add .
git commit -m "SinoSearch MVP: cross-lingual China search + RAG answers"
gh repo create sinosearch --public --source=. --push   # or create on github.com, then:
git remote add origin https://github.com/<you>/sinosearch.git && git push -u origin main
```

Notes: `.gitignore` excludes `*.db` and caches — users rebuild the index with
`python -m sinosearch.seed_ingest`. Never commit `OPENAI_API_KEY`; everything is env-driven.
Optional deploy: Railway/Render/Fly.io with start command `uvicorn sinosearch.server:app
--host 0.0.0.0 --port $PORT`.

⚠️ Legal/ops: keep the crawler polite (it honors robots.txt and rate-limits); Weibo/Zhihu/XHS
frequently block anonymous scraping — treat them as stretch goals or license data later.

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
