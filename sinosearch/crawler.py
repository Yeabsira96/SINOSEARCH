"""Polite incremental crawler for Chinese sources.

Guards: robots.txt (best effort), per-domain rate limit, same-domain link filter,
max-hops & max-pages budgets, dedupe via crawl_queue + content hash in ingest.
"""
from __future__ import annotations

import time
import urllib.robotparser as robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import settings
from .db import tx, enqueue, next_pending, set_queue_status
from .ingest import ingest_html

_SEED_SOURCES = [
    # Curated starting points — replace/extend with your target list.
    # ("https://www.gov.cn/", 0),
]


class Crawler:
    def __init__(self, max_pages: int = 50, max_hops: int = 2,
                 allowed_domains: list[str] | None = None):
        self.max_pages = max_pages
        self.max_hops = max_hops
        self.allowed = set(allowed_domains or [])
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_hit: dict[str, float] = {}

    # ---- politeness -----------------------------------------------------
    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _robots_ok(self, url: str) -> bool:
        d = self._domain(url)
        rp = self._robots.get(d)
        if rp is None:
            rp = robotparser.RobotFileParser()
            rp.set_url(f"{urlparse(url).scheme}://{d}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp.allow_all = True  # unreachable robots.txt -> conservative default: allow public GET
            self._robots[d] = rp
        return rp.can_fetch(settings.user_agent, url)

    def _wait(self, url: str) -> None:
        d = self._domain(url)
        elapsed = time.time() - self._last_hit.get(d, 0.0)
        if elapsed < settings.crawl_delay_per_domain_s:
            time.sleep(settings.crawl_delay_per_domain_s - elapsed)
        self._last_hit[d] = time.time()

    def _in_scope(self, url: str) -> bool:
        d = self._domain(url)
        if not d:
            return False
        if self.allowed and d not in self.allowed:
            return False
        return True

    # ---- crawling -------------------------------------------------------
    def fetch(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and not resp.text[:200].lstrip().startswith("<"):
                return None
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException:
            return None

    def extract_links(self, html: str, base: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            u = urljoin(base, a["href"]).split("#")[0]
            if urlparse(u).scheme in ("http", "https") and self._in_scope(u):
                links.append(u)
        return links

    def run(self, seeds: list[tuple[str, int]] | None = None,
            display_sources: dict[str, str] | None = None) -> int:
        """BFS from queue. Returns pages ingested."""
        seeds = seeds or _SEED_SOURCES
        display_sources = display_sources or {}
        with tx() as conn:
            for url, hops in seeds:
                enqueue(conn, url, self._domain(url), hops)
        ingested = 0
        while ingested < self.max_pages:
            with tx() as conn:
                batch = next_pending(conn, 1)
                if not batch:
                    break
                row = batch[0]
                url, hops = row["url"], row["hops"]
            if hops > self.max_hops:
                with tx() as conn:
                    set_queue_status(conn, url, "skipped", "max_hops")
                continue
            if not self._robots_ok(url):
                with tx() as conn:
                    set_queue_status(conn, url, "skipped", "robots")
                continue
            self._wait(url)
            html = self.fetch(url)
            if html is None:
                with tx() as conn:
                    set_queue_status(conn, url, "failed", "fetch")
                continue
            n = ingest_html(url, html,
                            source_name=display_sources.get(self._domain(url),
                                                            self._domain(url)))
            ingested += 1 if n else 0
            new_links = self.extract_links(html, url)
            with tx() as conn:
                set_queue_status(conn, url, "done")
                for l in new_links:
                    enqueue(conn, l, self._domain(l), hops + 1)
        return ingested
