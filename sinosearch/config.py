"""Central settings, env-driven (prefix SINO_)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    # storage
    db_path: str = os.getenv("SINO_DB_PATH", "sinosearch.db")
    static_dir: str = os.getenv("SINO_STATIC_DIR", "static")

    # crawling
    user_agent: str = os.getenv(
        "SINO_UA", "SinoSearchBot/0.1 (+contact: you@example.com)"
    )
    crawl_delay_per_domain_s: float = float(os.getenv("SINO_CRAWL_DELAY", "2.0"))
    max_chunk_chars: int = int(os.getenv("SINO_CHUNK_CHARS", "500"))
    chunk_overlap_chars: int = int(os.getenv("SINO_CHUNK_OVERLAP", "80"))

    # retrieval
    top_k_per_lane: int = int(os.getenv("SINO_TOP_K", "30"))
    final_top_k: int = int(os.getenv("SINO_FINAL_K", "6"))
    rrf_k: int = 60

    # embeddings: "hash" (offline deterministic demo), "hf" (local multilingual
    # model), or "openai" (API). hash keeps the MVP runnable with zero downloads.
    embed_provider: str = os.getenv("SINO_EMBED_PROVIDER", "hash")
    embed_model: str = os.getenv(
        "SINO_EMBED_MODEL", "intfloat/text2vec-multilingual-large"
    )
    embed_dim: int = int(os.getenv("SINO_EMBED_DIM", "256"))

    # translation: "noop" (offline) or "openai". Query EN->ZH matters most for recall.
    translate_provider: str = os.getenv("SINO_TRANSLATE_PROVIDER", "noop")

    # answer synthesis: "echo" (offline extractive) or "openai" (generative RAG)
    llm_provider: str = os.getenv("SINO_LLM_PROVIDER", "echo")
    llm_model: str = os.getenv("SINO_LLM_MODEL", "gpt-4o-mini")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    seed_dir: str = os.getenv("SINO_SEED_DIR", "seed_data")


settings = Settings()
