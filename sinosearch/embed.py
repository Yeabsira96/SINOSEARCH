"""Multilingual embeddings. Providers: hash (offline), hf, openai."""
from __future__ import annotations

import hashlib
import math

import numpy as np

from .config import settings

_hf_model = None


def _hash_embed(text: str, dim: int) -> np.ndarray:
    """Deterministic bag-of-ngram hashed embedding.

    Not semantic — but it makes the vector lane behave like a soft term-matcher
    so the full hybrid pipeline is testable offline. Replace with a real
    multilingual model in prod (see embed_hf / embed_openai).
    """
    vec = np.zeros(dim, dtype=np.float32)
    toks = text.lower().split()
    for t in toks:
        h = int.from_bytes(hashlib.blake2b(t.encode("utf-8"), digest_size=8).digest(),
                           "big")
        idx = h % dim
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


def embed_hf(texts: list[str]) -> list[list[float]]:
    global _hf_model
    if _hf_model is None:
        from sentence_transformers import SentenceTransformer  # lazy import
        _hf_model = SentenceTransformer(settings.embed_model)
    emb = _hf_model.encode(texts, normalize_embeddings=True)
    return [e.tolist() for e in emb]


def embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI  # lazy import
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url)
    res = client.embeddings.create(model="text-embedding-3-small", input=texts)
    out = []
    for d in res.data:
        v = np.array(d.embedding, dtype=np.float32)
        out.append((v / np.linalg.norm(v)).tolist())
    return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    p = settings.embed_provider
    if p == "hf":
        return embed_hf(texts)
    if p == "openai":
        return embed_openai(texts)
    dim = settings.embed_dim
    return [_hash_embed(t, dim).tolist() for t in texts]


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_topk(query_vec: list[float], candidates: dict[int, list[float]],
                k: int) -> list[tuple[int, float]]:
    if not candidates:
        return []
    q = np.asarray(query_vec, dtype=np.float32)
    ids = list(candidates.keys())
    M = np.vstack([candidates[i] for i in ids]).astype(np.float32)
    sims = M @ q  # vectors stored normalized -> dot == cosine
    order = np.argsort(-sims)[:k]
    return [(ids[int(i)], float(sims[int(i)])) for i in order]
