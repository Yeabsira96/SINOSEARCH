"""Answer synthesis (RAG): retrieve Chinese chunks, produce an English answer with citations.

Providers:
  echo   — offline extractive fallback: assembled ZH snippets + EN gloss (no API key needed)
  openai — generative RAG: LLM reads top-K Chinese chunks, writes cited English answer
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import settings
from .gloss import literal_en
from .index import Hit, hybrid_search
from .translate import translate

_CJK_RUN = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff，。、；：“”！？（）\s]*")


def _zh_spans(text: str, max_len: int = 160) -> list[str]:
    """Pull the most informative-looking CJK spans out of a chunk (for echo mode)."""
    spans = [s.strip(" ，。、；：") for s in _CJK_RUN.findall(text)]
    spans = [s for s in spans if len(s) >= 8]
    spans.sort(key=len, reverse=True)
    return [s[:max_len] for s in spans[:2]]


@dataclass
class Answer:
    query: str                 # original user query
    query_zh: str              # translated query actually used for retrieval
    text: str                  # English answer
    citations: list[dict] = field(default_factory=list)
    mode: str = "echo"


def _build_prompt(query: str, hits: list[Hit]) -> list[dict]:
    context = "\n\n".join(
        f"[{i}] 来源: {h.source_name or h.domain} ({h.url})\n标题: {h.title}\n内容: {h.text}"
        for i, h in enumerate(hits, 1)
    )
    return [
        {"role": "system", "content": (
            "You are SinoSearch, an assistant answering questions about China using ONLY "
            "the provided Chinese-language sources. Write your answer in clear English. "
            "Cite sources inline with bracketed numbers like [1]. If sources conflict, say so. "
            "If the sources don't contain the answer, state that plainly. Never invent URLs."
        )},
        {"role": "user", "content": f"Question: {query}\n\nSources:\n{context}"},
    ]


def _synthesize_openai(query: str, hits: list[Hit]) -> str:
    from openai import OpenAI  # lazy import
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    resp = client.chat.completions.create(
        model=settings.llm_model, messages=_build_prompt(query, hits), temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def _synthesize_echo(query: str, hits: list[Hit]) -> str:
    """Offline extractive answer: tell the user what the top Chinese sources say,
    verbatim + English gloss (dictionary-based, no API key needed)."""
    if not hits:
        return (f"No indexed Chinese sources matched “{query}”. Try broader terms, "
                "or ingest more pages.")
    lines = [f"Top Chinese sources found for “{query}” (extractive preview — set "
             "SINO_LLM_PROVIDER=openai for a synthesized English answer):"]
    for i, h in enumerate(hits, 1):
        spans = _zh_spans(h.text)
        snippet = " … ".join(spans) if spans else h.text[:160]
        en = literal_en(snippet, 220)
        lines.append(f"[{i}] {snippet}\n     English: {en}")
    return "\n\n".join(lines)


def answer_query(query: str, top_k: int | None = None) -> Answer:
    """Full loop: EN->ZH query translation -> hybrid search -> synthesis with citations."""
    query_zh = translate(query, "zh")
    hits = hybrid_search(query_zh, final_k=top_k)
    from .bilingual import decorate          # avoid circular import at module load
    citations = decorate(hits)

    if settings.llm_provider == "openai" and settings.openai_api_key:
        text, mode = _synthesize_openai(query, hits), "openai"
    else:
        text, mode = _synthesize_echo(query, hits), "echo"

    return Answer(query=query, query_zh=query_zh, text=text, citations=citations, mode=mode)
