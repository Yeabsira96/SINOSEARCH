"""Bilingual result decoration: attach English meaning to every Chinese hit.

For each Hit we produce:
  snippet_en   — readable English of the snippet. Uses a cached MT translation if
                 present, otherwise an offline dictionary gloss (gloss.literal_en),
                 so *something meaningful in English* always ships to the UI even
                 with zero API keys configured.
  title_en     — English rendering of the page title.
  pinyin       — tone-pinyin of the snippet's leading CJK run (pronunciation help).
  gloss_inline — word-for-word bracketed expansion (上海[Shanghai] 落户[settle…])
                 shown behind a "word-by-word" toggle for learners/verification.

MT translations that succeed are cached in chunk_translations so repeat searches
don't re-pay the translation provider.
"""
from __future__ import annotations

from .config import settings
from .db import tx, get_chunk_translation, put_chunk_translation
from .gloss import gloss_sentence, literal_en, romanize
import sinosearch.gloss_extra  # noqa: F401  (merges extra terms into the dictionary)
from .translate import translate


def _looks_chinese(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _en_for_chunk(chunk_id: int, zh_text: str) -> tuple[str, str]:
    """Return (english_text, source_tag) where tag is mt|gloss|same."""
    if not _looks_chinese(zh_text):
        return "", "same"          # already English — UI hides the EN block
    with tx() as conn:
        cached = get_chunk_translation(conn, chunk_id)
    if cached:
        return cached, "mt"
    # try real MT once (noop provider returns text unchanged -> detect & skip)
    if settings.translate_provider != "noop":
        try:
            en = translate(zh_text, "en")
            if en and en.strip() != zh_text.strip():
                with tx() as conn:
                    put_chunk_translation(conn, chunk_id, en, settings.translate_provider)
                return en, "mt"
        except Exception:
            pass
    return literal_en(zh_text), "gloss"


def decorate(hits) -> list[dict]:
    """Turn Hit objects into bilingual dicts ready for JSON responses."""
    out = []
    for i, h in enumerate(hits, 1):
        snippet_zh = h.text[:300]
        en, src = _en_for_chunk(h.chunk_id, snippet_zh)
        title_en = literal_en(h.title, 120) if _looks_chinese(h.title) else ""
        out.append({
            "n": i,
            "title": h.title,
            "title_en": title_en,
            "url": h.url,
            "domain": h.domain,
            "source": h.source_name,
            "published": h.published,
            "snippet_zh": snippet_zh,
            "snippet_en": en,
            "en_source": src,                      # mt | gloss | same
            "gloss_inline": gloss_sentence(snippet_zh, 160) if src == "gloss" else "",
            "pinyin": romanize(snippet_zh[:40]),
            "score": round(h.score, 5),
            "lane": h.lane,
        })
    return out
