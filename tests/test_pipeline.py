"""End-to-end pipeline tests: normalize -> tokenize/chunk -> ingest -> hybrid search -> answer."""
from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("SINO_DB_PATH", tempfile.mktemp(suffix=".db"))

from sinosearch.db import init_db, tx                      # noqa: E402
from sinosearch.normalize import html_to_text, tokenize, chunk_text, body_hash  # noqa: E402
from sinosearch.ingest import ingest_html                  # noqa: E402
from sinosearch.index import bm25_search, vector_search, hybrid_search, rrf_fuse  # noqa: E402
from sinosearch.translate import translate                 # noqa: E402
from sinosearch.answer import answer_query                 # noqa: E402

PAGE = """
<html><head><title>上海落户政策：居转户需要几年？</title></head><body>
<nav>无关导航</nav>
<main>
<p>持有上海市居住证满八年，即累计84个月，可以申请居转户。</p>
<p>社保和纳税记录必须连续，最近三年社保基数达到社平工资两倍以上。</p>
<p>临港重点产业人才可将居转户年限缩短为五年。</p>
</main></body></html>
""".strip()


class TestNormalize(unittest.TestCase):
    def test_html_to_text_stips_boilerplate(self):
        title, text = html_to_text(PAGE)
        self.assertIn("居转户", title)
        self.assertNotIn("无关导航", text)

    def test_cjk_tokenizer_bigrams(self):
        toks = tokenize("上海落户").split()
        self.assertIn("上海", toks)   # bigram
        self.assertIn("落", toks)     # unigram
        self.assertIn("海落", toks)   # sliding bigram
        self.assertNotIn("户落", toks)  # order matters: no reversed bigrams

    def test_chunking_bounds(self):
        long = "句。" * 1000
        chunks = chunk_text(long, max_chars=200)
        self.assertTrue(all(len(c) <= 220 for c in chunks))

    def test_hash_dedupe(self):
        self.assertEqual(body_hash("你好 世界"), body_hash("你好世界"))


class TestIngestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.n = ingest_html("https://zhihu.example/q1", PAGE, source_name="知乎")
        ingest_html("https://gov.example/g1",
                    "<html><head><title>新能源汽车补贴</title></head><body>"
                    "<article><p>电动车购置补贴退坡但购置税免征延续。</p></article></body></html>",
                    source_name="中国政府网")

    def test_ingest_dedupes_unchanged_doc(self):
        # same URL + same content hash -> re-ingest adds nothing (incremental crawl behavior)
        self.assertEqual(ingest_html("https://zhihu.example/q1", PAGE), 0)

    def test_bm25_lane(self):
        hits = bm25_search("居转户 社保", k=10)
        self.assertTrue(hits)

    def test_vector_lane(self):
        hits = vector_search("居转户", k=10)
        self.assertTrue(hits)

    def test_hybrid_finds_relevant_doc_first(self):
        hits = hybrid_search("上海 居转户 几年")
        self.assertTrue(hits)
        self.assertIn("居转户", hits[0].title)
        self.assertEqual(hits[0].source_name, "知乎")

    def test_rrf_math(self):
        fused = rrf_fuse([[(1, 9.0)], [(1, 0.9), (2, 0.8)]], k_rrf=60)
        self.assertAlmostEqual(fused[1], 2 / 61.0, places=6)
        self.assertGreater(fused[1], fused[2])


class TestCrossLingual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        ingest_html("https://zhihu.example/q1", PAGE, source_name="知乎")

    def test_en_query_translates_with_glossary(self):
        zh = translate("How do I get a Shanghai hukou?", "zh")
        self.assertIn("上海", zh)
        self.assertIn("落户", zh)

    def test_answer_end_to_end(self):
        a = answer_query("Shanghai hukou policy requirements")
        self.assertTrue(a.citations)
        self.assertIn("居转户", a.text + " ".join(c["snippet_zh"] for c in a.citations))
        self.assertEqual(a.mode, "echo")  # offline default
        for c in a.citations:
            self.assertTrue(c["url"].startswith("http"))


class TestServer(unittest.TestCase):
    def test_api(self):
        from fastapi.testclient import TestClient
        from sinosearch.server import app
        client = TestClient(app)
        self.assertTrue(client.get("/api/health").json()["ok"])
        r = client.post("/api/search", json={"query": "上海落户"}).json()
        self.assertTrue(r["results"])
        r = client.post("/api/answer", json={"query": "shanghai hukou"}).json()
        self.assertTrue(r["citations"])
        self.assertTrue(client.get("/").status_code in (200, 404))


if __name__ == "__main__":
    unittest.main()
