"""Web-source adapters: Baidu + social platforms, merged into the local index.

Design (honest about what is reachable from a laptop):
  * BAIDU      — `https://www.baidu.com/s?wd=...` is fetchable with a plain UA.
                 We parse the result page, extract organic hits
                 (title / URL / raw Chinese snippet), and *optionally* visit each
                 result URL to ingest its full text into our own index. This is
                 "include data from Baidu": Baidu becomes a discovery lane whose
                 findings are merged with curated-source crawl results.
  * SOCIAL     — Weibo/Zhihu/Xiaohongshu/Bilibili aggressively bot-wall anonymous
                 HTML. Rather than fake it, we (a) keep the offline seed posts in
                 seed_data/ as representative samples, (b) expose per-platform
                 search URLs so the UI can deep-link ("open live on Weibo ↗"), and
                 (c) ingest any user-supplied export/HTML via --ingest-dir.
  * LIVE=0     — everything degrades gracefully: no network calls, seed corpus only.

Nothing here touches the retrieval core; whatever gets ingested simply becomes
searchable through the same hybrid BM25+vector pipeline.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Social platforms: name -> (display, live-search URL template {query})
SOCIAL_PLATFORMS = {
    "weibo":       {"label": "微博 Weibo",       "search": "https://s.weibo.com/weibo?q={query}"},
    "zhihu":       {"label": "知乎 Zhihu",       "search": "https://www.zhihu.com/search?type=content&q={query}"},
    "xiaohongshu": {"label": "小红书 RED",        "search": "https://www.xiaohongshu.com/search_result?keyword={query}"},
    "bilibili":    {"label": "B站 Bilibili",     "search": "https://search.bilibili.com/all?keyword={query}"},
    "douyin":      {"label": "抖音 Douyin",      "search": "https://www.douyin.com/search/{query}"},
    "tieba":       {"label": "百度贴吧 Tieba",    "search": "https://tieba.baidu.com/f/search/res?ie=utf-8&qw={query}"},
}


@dataclass
class WebHit:
    title: str
    url: str
    snippet: str
    source: str          # e.g. "Baidu" or domain


def _get(url: str, timeout: int = 10) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Accept-Language": "zh-CN,zh;q=0.9"},
                         timeout=timeout)
        if r.status_code == 200 and "百度安全验证" not in r.text[:2000]:
            return r.text
    except Exception:
        pass
    return None


def baidu_search(query: str, max_results: int = 8) -> list[WebHit]:
    """Scrape Baidu web results for a Chinese query. Returns [] on bot-wall/offline."""
    q = urllib.parse.quote(query)
    html = _get(f"https://www.baidu.com/s?wd={q}&rn={max(10, max_results)}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    hits: list[WebHit] = []
    seen: set[str] = set()
    for h3 in soup.select("h3"):
        a = h3.find("a")
        if not a or not a.get("href"):
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        container = h3.find_parent("div")
        snippet = ""
        if container:
            for sel in ("div.content-right_2s-H4 span", "div.c-span-last",
                        "span.c-text-muted_1tw20", "div.c-abstract"):
                el = container.select_one(sel)
                if el:
                    snippet = el.get_text(" ", strip=True)
                    break
        url = a["href"]
        # Baidu wraps real URLs in /s?wd=... redirect links; keep as-is but dedupe
        if url.startswith("http://") or url.startswith("https://"):
            key = url.split("&")[0]
            if key in seen:
                continue
            seen.add(key)
            hits.append(WebHit(title=title, url=url, snippet=snippet, source="Baidu"))
        if len(hits) >= max_results:
            break
    return hits


def ingest_webhit(hit: WebHit, *, follow: bool = True) -> int:
    """Add a Baidu/social hit to our index. With follow=True we also fetch the
    target page's full text (best effort; many CN sites bot-wall)."""
    from .ingest import ingest_html
    body = hit.snippet or hit.title
    domain = ""
    if follow and hit.url.startswith("http"):
        html = _get(hit.url, timeout=8)
        if html:
            body = html
            try:
                domain = urllib.parse.urlsplit(hit.url).netloc
            except Exception:
                pass
    if not domain:
        try:
            domain = urllib.parse.urlsplit(hit.url).netloc
        except Exception:
            domain = "baidu"
    src = "Baidu 网页搜索" if hit.source == "Baidu" else hit.source
    return ingest_html(hit.url, body, source_name=src, domain=domain)


def social_links(query: str) -> list[dict]:
    """Deep-links for live social search (platform walls make scraping unreliable)."""
    q = urllib.parse.quote(query)
    return [{"key": k, "label": v["label"], "url": v["search"].format(query=q)}
            for k, v in SOCIAL_PLATFORMS.items()]


def enrich_with_baidu(query_zh: str, max_results: int = 5,
                      follow: bool = False, delay_s: float = 1.0) -> dict:
    """One-call helper used by the server: search Baidu, optionally ingest,
    report what happened. Never raises."""
    out = {"attempted": True, "hits": [], "indexed_chunks": 0, "note": ""}
    hits = baidu_search(query_zh, max_results=max_results)
    if not hits:
        out["note"] = ("Baidu returned nothing usable (bot-check or offline). "
                       "Showing curated sources only.")
        return out
    total = 0
    for h in hits:
        if follow:
            total += ingest_webhit(h)
            time.sleep(delay_s)   # politeness
        out["hits"].append({"title": h.title, "url": h.url,
                            "snippet": h.snippet[:200], "source": h.source})
    out["indexed_chunks"] = total
    out["note"] = (f"Baidu gave {len(hits)} results"
                   + (f", ingested {total} chunks" if follow else " (preview only, not indexed)"))
    return out
