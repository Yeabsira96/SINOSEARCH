"""Curated registry of the most-visited / most-researchable Chinese websites.

Tailored for MARKET-EXPLORATION RESEARCH: someone expanding an overseas business
into China should be able to ask (in English) about consumer trends, competitor
companies, regulation, licensing, e-commerce platforms, local sentiment, etc.,
and retrieve answers sourced from native Chinese sites — not Western media.

Categories used (see `crawl --category`):
  gov        policy, laws, licensing, business registration, stats
  business   company databases, funding news, industry reports
  ecommerce  platform marketplaces & seller/trend data
  social     UGC sentiment: what Chinese consumers actually say
  news       general + financial news
  local      city life / consumer guides (Xiaohongshu-style content mirrors)

Notes on accessibility (read before crawling):
  * Weibo/Zhihu/Xiaohongshu/Douyin heavily gate anonymous scraping; they often
    return login walls. For those, prefer their public WAP/mirror pages, RSS-ish
    list pages, or official API/newsroom endpoints. The crawler already skips
    non-HTML and honors robots.txt, so gated pages simply yield nothing.
  * gov.cn / stats.gov.cn / samr.gov.cn are crawl-friendly and authoritative —
    start there for anything regulatory.
  * Keep per-domain delay >= 2s and max_pages small while testing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str            # display name (used as source_name in docs table)
    domain: str          # netloc used for scope filtering
    seeds: tuple[str, ...]  # entry-point URLs to enqueue at hop 0
    category: str
    notes: str = ""


REGISTRY: list[Source] = [
    # ---------------- government / regulator / statistics ----------------
    Source("中国政府网", "www.gov.cn",
           ("https://www.gov.cn/",),
           "gov", "Policy announcements, state council decrees, licensing rules."),
    Source("国家统计局", "www.stats.gov.cn",
           ("https://www.stats.gov.cn/",),
           "gov", "Official macro / retail / demographic statistics."),
    Source("市场监管总局", "www.samr.gov.cn",
           ("https://www.samr.gov.cn/",),
           "gov", "Company registration, product standards, advertising law."),
    Source("商务部", "www.mofcom.gov.cn",
           ("https://www.mofcom.gov.cn/",),
           "gov", "Foreign investment, FIE (外商投资) rules, FTZ policy."),
    Source("上海市政府", "www.shanghai.gov.cn",
           ("https://www.shanghai.gov.cn/",),
           "gov", "Shanghai-specific permits, hukou, free-trade zone."),
    Source("北京市政府", "www.beijing.gov.cn",
           ("https://www.beijing.gov.cn/",),
           "gov", "Beijing licensing, tech-zone incentives."),

    # ---------------- business / startup / company intel -----------------
    Source("36氪", "36kr.com",
           ("https://36kr.com/", "https://36kr.com/newsflashes"),
           "business", "Startup + VC news, sector deep-dives, company profiles."),
    Source("虎嗅网", "www.huxiu.com",
           ("https://www.huxiu.com/",),
           "business", "Business analysis, consumer-brand teardowns."),
    Source("亿欧", "www.iyiou.com",
           ("https://www.iyiou.com/",),
           "business", "Industry research reports (manufacturing, retail, auto)."),
    Source("界面新闻", "www.jiemian.com",
           ("https://www.jiemian.com/",),
           "news", "Financial/consumer reporting."),
    Source("财新网", "www.caixin.com",
           ("https://www.caixin.com/",),
           "news", "In-depth economic policy reporting (paywalled partly)."),

    # ---------------- e-commerce / consumer trends -----------------------
    Source("京东商学院资讯", "mtt.m.jd.com",
           ("https://mtt.m.jd.com/",),
           "ecommerce", "JD seller/marketplace trend articles."),
    Source("淘宝大学/生意参谋博客", "daxue.taobao.com",
           ("https://daxue.taobao.com/",),
           "ecommerce", "Taobao category trends, merchant guidance."),
    Source("拼多多商家社区", "mms.pinduoduo.com",
           ("https://mms.pinduoduo.com/",),
           "ecommerce", "PDD merchant rules & campaigns."),
    Source("小红书(公开页)", "www.xiaohongshu.com",
           ("https://www.xiaohongshu.com/explore",),
           "social", "Consumer sentiment; frequently gated — see module notes."),
    Source("微博热搜", "s.weibo.com",
           ("https://s.weibo.com/top/summary",),
           "social", "Live trending topics; API usually requires cookie."),
    Source("知乎", "www.zhihu.com",
           ("https://www.zhihu.com/topic",),
           "social", "Long-form Q&A on products, cities, careers, brands."),
    Source("百度贴吧", "tieba.baidu.com",
           ("https://tieba.baidu.com/",),
           "social", "Community threads by city / brand / hobby."),

    # ---------------- news / portals -------------------------------------
    Source("新华网", "www.news.cn",
           ("https://www.news.cn/",),
           "news", "State news agency; broad domestic coverage."),
    Source("人民网", "www.people.com.cn",
           ("http://www.people.com.cn/",),
           "news", "Party media; policy tone indicator."),
    Source("央视网", "news.cctv.com",
           ("https://news.cctv.com/",),
           "news", "TV network news portal."),
    Source("新浪新闻", "news.sina.com.cn",
           ("https://news.sina.com.cn/",),
           "news", "High-volume aggregator; good for keyword breadth."),
    Source("腾讯新闻", "news.qq.com",
           ("https://news.qq.com/",),
           "news", "Another high-volume aggregator."),
]

CATEGORIES = sorted({s.category for s in REGISTRY})


def sources_for(categories: list[str] | None = None,
                names: list[str] | None = None) -> list[Source]:
    out = []
    for s in REGISTRY:
        if categories and s.category not in categories:
            continue
        if names and s.name not in names and s.domain not in names:
            continue
        out.append(s)
    return out


def seed_pairs(srcs: list[Source]) -> list[tuple[str, int]]:
    """Flatten to (url, hops) pairs for Crawler.run()."""
    return [(u, 0) for s in srcs for u in s.seeds]


def display_map(srcs: list[Source]) -> dict[str, str]:
    """domain -> friendly name (crawler passes this as source_name)."""
    return {s.domain: s.name for s in srcs}
