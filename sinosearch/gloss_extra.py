"""Extra gloss terms merged into sinosearch.gloss.TERMS at import time.

Discovered by running the offline glosser over the seed corpus: these are the
high-frequency words that fell through to single-hanzi fallbacks. Keeping them
in a separate patch module avoids bloating gloss.py's giant literal.
"""
from . import gloss

EXTRA = {
    # gov / hukou phrasing
    "持有": "holding", "人员": "personnel", "申办": "apply for", "本市": "this municipality",
    "常住": "long-term resident", "依据": "based on", "年限": "years required",
    "取得": "obtain/receive", "不宜": "not suitable", "转户": "transfer hukou",
    "情形": "circumstances", "持证": "permit holder", "期间": "during the period",
    "技能": "skilled", "投资创业": "investment & entrepreneurship", "可放宽至": "can be relaxed to",
    "随迁": "move along (family transfer)", "配偶子女": "spouse and children",
    # zhihu EV post
    "回答": "answer", "作为": "as/a", "一个": "one/a", "提车": "take delivery of a car",
    "车主": "car owner", "我说": "I say", "一下": "a bit", "感受": "feelings/impressions",
    "国家": "state/national", "延续": "continued", "实际": "actual", "购车": "buy a car",
    "变化": "change", "没有": "no/not have", "想象": "imagine", "更大": "bigger",
    "更重要": "more importantly", "地方": "local area", "层面": "level/aspect",
    "为例": "taking as example", "置换": "trade-in", "纯电": "pure electric",
    "仍有": "still have", "部分": "part/some", "充电券": "charging voucher",
    "普遍": "widespread", "观点": "viewpoint", "低价": "low-priced", "微型车": "micro cars",
    "车型": "car model", "决策": "decision", "更多": "more", "智能化": "smart/intelligent features",
    "便利性": "convenience", "评论区": "comment section", "比亚迪": "BYD", "蔚来": "NIO",
    "讨论": "discussion", "热烈": "heated", "多数": "majority", "认为": "believe/think",
    "产业链": "industry chain", "具备": "possess", "自我造血": "self-sustaining",
    "依赖": "rely on", "生存": "survive", "渗透率": "penetration rate", "突破": "break through",
    "即使": "even if", "电车": "EV", "认知": "awareness/cognition",
    # 36kr luxury article
    "研究院": "research institute", "数据显示": "data shows", "内地": "mainland",
    "同比": "year-on-year", "收缩": "shrink", "出境游": "outbound travel",
    "恢复": "recover", "回流": "flow back", "巴黎": "Paris", "东京": "Tokyo",
    "本土": "local/homegrown", "信号": "signal", "复杂": "complex/mixed",
    "海南离岛": "Hainan offshore islands", "免税": "duty-free", "销售额": "sales revenue",
    "持续": "continues to", "二手": "secondhand", "中古店": "vintage/pre-owned shop",
    "交易": "transaction/trading", "画像": "profile/portrait", "岁": "years old",
    "盲目": "blindly", "追求": "chase/pursue", "大牌": "big brands", "转向": "shift toward",
    "品质": "quality", "黄金": "gold", "饰品": "jewelry/accessories", "保值": "retain value",
    "属性": "attribute", "暴涨": "surge", "老铺": "old established shop",
    "排队数小时": "queues for hours", "某": "a certain", "调研显示": "a survey shows",
    "世代": "generation", "更酷": "cooler", "品牌端": "brand side", "应对": "respond to",
    "加速": "accelerate", "开店": "open stores", "加码": "double down", "联名": "co-branding",
    "国货": "domestic brands", "美妆": "beauty/cosmetics", "高端": "high-end",
    "试探": "test/probe", "天花板": "ceiling", "共识": "consensus", "通路": "channel/route",
    "投放": "ad placement/spending", "进入市场": "enter the market",
    # xhs / weibo / casual posts
    "姐妹们": "girls/sisters", "避雷": "avoid pitfalls", "踩坑": "step into traps",
    "真实": "real/genuine", "分享": "share", "租房": "renting", "经历": "experience/story",
    "中介": "agent", "虚假": "fake", "房源": "listed property", "押金": "deposit",
    "退租": "end lease/move out", "扣钱": "deduct money", "合同条款": "contract clauses",
    "口头承诺": "verbal promise", "不靠谱": "unreliable", "平台投诉": "platform complaint",
    "客服": "customer service", "处理": "handle/deal with", "拖": "stall/drag",
    "更新": "update", "笔记": "notes/post", "收藏": "bookmark/save", "实用": "practical",
    "干货": "useful content (dry goods)", "小白": "newbie", "新手": "beginner",
    "攻略": "guide/walkthrough", "省钱": "save money", "花冤枉钱": "waste money on scams",
    "吐槽": "complain/roast", "官方": "official", "回应": "respond/reply", "热搜第一": "#1 on trending",
    "网友热议": "netizens discuss heatedly", "翻车": "fail/flip over (go wrong)",
    "种草": "get hooked/want it", "拔草": "finally buy after wanting", "回购": "repurchase",
    "测评": "hands-on review", "对比": "compare", "维度": "dimension/aspect",
    "性价比之王": "king of value for money", "踩雷无数": "hit countless landmines",
    "血泪教训": "lessons in blood and tears", "亲测": "personally tested",
    "有效": "effective", "无效": "ineffective", "推荐指数": "recommendation score",
    "适合": "suitable for", "不适合": "not suitable for", "人群": "group of people",
    "预算有限": "limited budget", "学生党": "students crowd", "上班族": "office workers",
    "打工人": "working stiffs", "通勤": "commute", "上班": "go to work", "下班": "off work",
    "午休": "lunch break", "周末": "weekend", "假期": "holiday/vacation",
    "出游": "go out traveling", "周边游": "nearby getaways", "短途": "short-distance",
    "长途": "long-distance", "自驾": "self-drive road trip", "高铁站": "railway station",
    "停车场": "parking lot", "堵车": "traffic jam", "错峰": "avoid peak times",
    "人从众": "crowds everywhere (lit. person-crowd-many)", "拍照打卡": "photo check-ins",
    "机位": "photo spots", "出片率高": "high chance of great photos", "滤镜参数": "filter settings",
    "氛围感拉满": "maximum vibes", "高级": "classy/premium", "平价": "affordable",
    "学生": "student", "老师": "teacher", "家长": "parents", "作业": "homework",
    "补课": "make-up classes/tutoring", "兴趣班": "hobby classes", "体育": "sports/PE",
    "考试": "exam", "录取": "admitted", "志愿": "application choices", "调剂": "reassignment",
    # misc connectors frequently missed
    "其中": "among them", "此外": "in addition", "目前": "so far/currently",
    "近年来": "in recent years", "随着": "along with/as", "导致": "lead to (result)",
    "造成": "cause", "引发": "trigger/spark", "受到": "receive (attention)",
    "欢迎": "welcome", "批评": "criticism", "支持": "support", "反对": "oppose",
    "表示": "express/state", "指出": "point out", "强调": "emphasize", "介绍": "introduce",
    "透露": "reveal/disclose", "预计": "estimate/expect", "达到": "reach", "超过": "exceed",
    "左右": "around/approx", "大约": "approximately", "接近": "close to", "高达": "as high as",
    "占比": "share/proportion", "比例": "ratio", "幅度": "margin/extent", "趋势明显": "clear trend",
    "有所": "somewhat", "明显上升": "notably rose", "明显下降": "notably fell",
    "分别": "respectively", "同时": "at the same time", "随后": "subsequently",
    "首先": "firstly", "其次": "secondly", "最后": "finally", "总之": "in short",
    "换句话说": "in other words", "值得注意的是": "worth noting", "据了解": "reportedly",
    "业内人士": "industry insiders", "专家表示": "experts state", "记者": "reporter",
    "采访": "interview", "报道": "coverage/report", "消息": "news/message",
    "来源": "source", "转载": "repost (cite source)", "原创": "original content",
}

def _merge():
    gloss.TERMS.update(EXTRA)
    # rebuild the longest-first segmentation index used by annotate()
    gloss._SORTED_TERMS = sorted(gloss.TERMS.keys(), key=len, reverse=True)

_merge()
