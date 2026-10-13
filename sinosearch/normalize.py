"""Normalization: HTML -> clean text, CJK-aware tokenization & chunking, dedupe hash."""
from __future__ import annotations

import hashlib
import re
import unicodedata

from bs4 import BeautifulSoup

from .config import settings

_CJK = r"\u4e00-\u9fff\u3400-\u4dbf"
_HAS_CJK = re.compile(f"[{_CJK}]")
_ASCII_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*")
_WS = re.compile(r"\s+")


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, main_text). Strips nav/script/style boilerplate."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav",
                     "aside", "form"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = root.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return title, "\n".join(lines)


def tokenize(text: str) -> str:
    """Index/query tokens: ASCII words lowercased; CJK runs -> unigrams + bigrams.

    Bigrams matter: single hanzi are too ambiguous (e.g. 方/案), bigrams like
    方案 carry the real signal. This gives usable Chinese BM25 without jieba;
    swap in jieba later behind this same interface.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if _HAS_CJK.match(ch):
            j = i
            while j < n and _HAS_CJK.match(text[j]):
                j += 1
            run = text[i:j]
            out.extend(run)                       # unigrams
            out.extend(run[k:k + 2] for k in range(len(run) - 1))  # bigrams
            i = j
        elif ch.isalnum():
            m = _ASCII_WORD.match(text, i)
            if m:
                out.append(m.group(0).lower())
                i = m.end()
            else:
                i += 1
        else:
            i += 1
    return " ".join(out)


def query_terms(text: str) -> list[str]:
    """Distinct tokens for building an FTS5 MATCH expression."""
    toks = tokenize(text).split()
    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def chunk_text(text: str, max_chars: int | None = None,
               overlap: int | None = None) -> list[str]:
    """Sentence-ish split on CJK/latin terminators, packed to <= max_chars."""
    max_chars = max_chars or settings.max_chunk_chars
    overlap = settings.chunk_overlap_chars if overlap is None else overlap
    sentences = re.split(r"(?<=[。！？；!?;\n])", text)
    sentences = [s for s in (x.strip() for x in sentences) if s]
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if len(s) > max_chars:                    # hard-split very long sentence
            if cur:
                chunks.append(cur)
                cur = ""
            for k in range(0, len(s), max_chars - overlap):
                pieces = s[k:k + max_chars]
                if pieces:
                    chunks.append(pieces)
            continue
        if len(cur) + len(s) + 1 <= max_chars:
            cur = f"{cur} {s}".strip()
        else:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            cur = f"{tail} {s}".strip() if tail else s
    if cur:
        chunks.append(cur)
    return chunks or ([text] if text else [])


def normalize_for_hash(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return _WS.sub("", text)


def body_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()[:16]
