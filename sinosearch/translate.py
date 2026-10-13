"""Machine translation, pluggable. Core UX trick: translate the QUERY EN->ZH so BM25
hits Chinese text; translate SNIPPETS ZH->EN so users can verify before clicking.

Providers: noop (offline passthrough) | openai. Add DeepL/Google here later.
"""
from __future__ import annotations

from .config import settings

# Tiny offline glossary so the demo corpus behaves sensibly without an API key.
_DEMO_EN2ZH = {
    "shanghai": "上海", "hukou": "落户", "residence permit": "居住证",
    "visa": "签证", "tax": "税务", "ev": "电动车", "electric vehicle": "新能源汽车",
    "subsidy": "补贴", "subsidies": "补贴", "housing fund": "公积金",
    "property": "房产", "school": "学区", "education": "教育",
    "healthcode": "健康码", "health code": "健康码", "payment": "支付",
    "mobile payment": "移动支付", "alipay": "支付宝", "wechat": "微信",
    "luxury": "奢侈品", "consumer": "消费", "shopping": "购物",
    "coffee": "咖啡", "tea": "茶", "startup": "创业", "market": "市场",
    "policy": "政策", "regulation": "法规", "foreigner": "外国人",
    "rent": "租房", "apartment": "公寓", "internet": "互联网",
    # --- market-expansion / business-research vocabulary (EN -> ZH) ---
    "market entry": "市场准入", "foreign investment": "外商投资",
    "wfoe": "外商独资企业", "negative list": "负面清单",
    "regulation": "监管", "competitor": "竞争对手", "competition": "竞争",
    "franchise": "加盟", "ecommerce": "电商", "e-commerce": "电商",
    "tmall": "天猫", "taobao": "淘宝", "jd": "京东", "pinduoduo": "拼多多",
    "consumer": "消费者", "trend": "趋势", "trends": "趋势",
    "pricing": "定价", "license": "许可", "licensing": "牌照",
    "icp": "备案", "trademark": "商标", "distributor": "经销商",
    "business": "商业", "company": "公司", "startup": "初创公司",
    "funding": "融资", "investment": "投资", "retail": "零售",
    "logistics": "物流", "tax": "税收", "brand": "品牌",
}


def _noop_translate(text: str, target_lang: str) -> str:
    if target_lang != "zh":
        return text
    low = text.lower()
    hits = sorted(
        ((en, zh) for en, zh in _DEMO_EN2ZH.items() if en in low),
        key=lambda kv: -len(kv[0]),
    )
    if not hits:
        return text
    parts = " ".join(zh for _, zh in hits[:4])
    return f"{parts} {text}"


def _openai_translate(text: str, target_lang: str) -> str:
    from openai import OpenAI  # lazy import
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url)
    name = {"zh": "Simplified Chinese", "en": "English"}.get(target_lang, target_lang)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{
            "role": "system",
            "content": f"Translate the user text to {name}. Output ONLY the translation.",
        }, {"role": "user", "content": text}],
        temperature=0,
    )
    return (resp.choices[0].message.content or text).strip()


def translate(text: str, target_lang: str) -> str:
    if not text.strip():
        return text
    p = settings.translate_provider
    try:
        if p == "openai":
            return _openai_translate(text, target_lang)
    except Exception:
        pass  # graceful degrade: retrieval still runs on original query
    return _noop_translate(text, target_lang)


def expand_query_en_to_zh(query: str) -> str:
    """Return combined query text: original + Chinese translation (for both lanes)."""
    zh = translate(query, "zh")
    if zh.strip().lower() == query.strip().lower():
        return query
    return f"{query} {zh}"
