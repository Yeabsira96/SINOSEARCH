/* SinoSearch front-end v2 — bilingual, dual-mode (casual search + deep research).
   Talks to /api/search and /api/answer; no build step, no dependencies. */
"use strict";

let MODE = "search";          // 'search' | 'answer'
let LANG = "both";            // 'both' | 'en'
let lastPayload = null;       // cache for re-rendering language view

const LANES = [
  { dot: "d-life",     zh: "上海落户政策", en: "Shanghai hukou policy" },
  { dot: "d-life",     zh: "外国人办银行卡", en: "foreigner bank account" },
  { dot: "d-life",     zh: "免签过境72小时", en: "72h visa-free transit" },
  { dot: "d-social",   zh: "奶茶品牌推荐", en: "milk tea brands ranked" },
  { dot: "d-social",   zh: "小红书 露营攻略", en: "RED camping guide" },
  { dot: "d-business", zh: "咖啡市场 行业报告", en: "coffee market industry report" },
  { dot: "d-business", zh: "外商独资 WFOE 注册", en: "WFOE registration" },
  { dot: "d-research", zh: "新能源汽车销量", en: "NEV sales statistics" },
  { dot: "d-research", zh: "个人信息保护法", en: "PIPL data law" },
];

const esc = s => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function goQ(q) {                       // safe click handler for dynamic queries
  const i = document.getElementById("q"); i.value = q; run(q);
}
window.goQ = goQ;

function setMode(m) {
  MODE = m;
  document.getElementById("m-search").classList.toggle("on", m === "search");
  document.getElementById("m-answer").classList.toggle("on", m === "answer");
  document.getElementById("goBtn").textContent = m === "search" ? "Search" : "Research";
  document.getElementById("modehint").textContent = m === "search"
    ? "Fast bilingual retrieval — great for everyday questions and quick facts."
    : "Reads the top Chinese sources and writes a cited English brief — for deeper research.";
  if (lastPayload && lastPayload.q) run(lastPayload.q);
}

function setLang(l) {
  LANG = l;
  document.getElementById("lg-both").classList.toggle("on", l === "both");
  document.getElementById("lg-en").classList.toggle("on", l === "en");
  if (lastPayload) render(lastPayload);
}

function doSubmit(ev) {
  ev.preventDefault();
  const q = document.getElementById("q").value.trim();
  if (q) run(q);
  closeAC();
  return false;
}

async function run(q) {
  document.getElementById("q").value = q;
  const box = document.getElementById("results");
  box.innerHTML = `<div class="empty"><div class="big">🐼</div>Searching Chinese sources…</div>`;
  const baidu = document.getElementById("baiduToggle").checked ? 1 : 0;
  const ep = MODE === "answer" ? "/api/answer" : "/api/search";
  try {
    const r = await fetch(`${ep}?q=${encodeURIComponent(q)}&baidu=${baidu}`);
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    lastPayload = data;
    render(data);
  } catch (e) {
    box.innerHTML = `<div class="err">Error: ${esc(String(e))}</div>`;
  }
}

function badgeFor(item) {
  const d = (item.domain || "") + (item.source || "");
  if (/gov\.cn|政府|国务院/.test(d)) return ["b-gov", "GOV"];
  if (/微博|weibo|知乎|zhihu|小红书|xhs|reddit|bilibili|douyin|贴吧/.test(d)) return ["b-social", "SOCIAL"];
  if (/36kr|界面|jiemian|caixin|财新|ebiz|电商|科技/.test(d)) return ["b-biz", "BIZ-PRESS"];
  if (/新闻|news|people| xinhua|新浪|sohu|163/.test(d)) return ["b-news", "NEWS"];
  if (/baidu/i.test(item.source || "")) return ["b-web", "BAIDU"];
  return ["b-news", "WEB"];
}

function resultCard(it) {
  const [bcls, blabel] = badgeFor(it);
  const showZh = LANG === "both";
  const enBlock = it.snippet_en ? `
    <div class="snip-en"><span class="lbl">${it.en_source === "mt" ? "ENGLISH TRANSLATION" : "ENGLISH MEANING (dictionary gloss)"}</span>${esc(it.snippet_en)}</div>` : "";
  const titleEn = it.title_en ? `<p class="title-en">“${esc(it.title_en)}”</p>` : "";
  const gloss = it.gloss_inline ? `
    <button class="tinybtn" onclick="this.nextElementSibling.classList.toggle('show')">word-by-word ⇄</button>
    <div class="gloss">${esc(it.gloss_inline)}</div>` : "";
  const py = it.pinyin ? `<div class="py">🔊 ${esc(it.pinyin)}</div>` : "";
  return `
  <article class="card"><div class="inner">
    <span class="srcbadge ${bcls}">${blabel}</span>
    <h3 class="title-zh" data-url="${esc(it.url)}">${esc(it.title)}</h3>
    ${LANG === "both" ? titleEn : ""}
    <div class="urlrow">
      <a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.domain || it.url)}</a>
      ${it.source ? `<span class="pill">${esc(it.source)}</span>` : ""}
      ${it.published ? `<span class="pill">${esc(it.published.slice(0, 10))}</span>` : ""}
      <span class="pill">lane: ${esc(it.lane)}</span>
    </div>
    ${showZh ? `<div class="snip-zh">${esc(it.snippet_zh)}</div>` : ""}
    ${enBlock}${showZh ? gloss + py : ""}
  </div></article>`;
}

function render(data) {
  const box = document.getElementById("results");
  let html = "";

  // meta line: what query was actually searched
  const qq = data.query_zh ? `searched as <span class="qq">${esc(data.query_zh)}</span>` : "";
  const n = (data.results || data.citations || []).length;
  html += `<div class="meta">${n} bilingual result${n === 1 ? "" : "s"} from curated Chinese index ${qq} · ${(data.live ? "LIVE mode on" : "offline corpus")}</div>`;

  // deep-research answer card
  if (MODE === "answer" && data.text) {
    html += `<div class="answer-card"><div class="answer-inner">
      <h3>🧠 Research brief ${data.answer_mode === "openai" ? "(LLM synthesis)" : "(extractive preview)"}</h3>
      <div class="answer-text">${esc(data.text)}</div></div></div>`;
  }

  // Baidu lane
  if (data.baidu && data.baidu.attempted) {
    if (data.baidu.hits && data.baidu.hits.length) {
      html += `<div class="meta" style="margin-top:14px">🔵 From Baidu live: ${esc(data.baidu.note)}</div>`;
      html += data.baidu.hits.map(h => `
        <article class="card"><div class="inner">
          <span class="srcbadge b-web">BAIDU</span>
          <h3 class="title-zh" data-url="${esc(h.url)}">${esc(h.title)}</h3>
          <div class="urlrow"><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.url.slice(0, 80))}…</a></div>
          <div class="snip-zh">${esc(h.snippet)}</div>
        </div></article>`).join("");
    } else {
      html += `<div class="meta">🔵 Baidu: ${esc(data.baidu.note || "no live results merged")}</div>`;
    }
  }

  // social deep-links bar
  if (data.social_links && data.social_links.length) {
    html += `<div class="socialbar"><div class="row"><span class="lbl">Open live on social ↗</span>` +
      data.social_links.map(s => `<a class="soc" target="_blank" rel="noopener" href="${esc(s.url)}">${esc(s.label)}</a>`).join("") +
      `</div></div>`;
  }

  // main results
  const items = data.results || data.citations || [];
  html += items.map(resultCard).join("");
  if (!items.length && MODE !== "answer") {
    html += `<div class="empty"><div class="big">🤷</div>No indexed matches. Try different wording, toggle Deep Research, or ingest more pages with <code>python -m sinosearch.cli crawl --live</code>.</div>`;
  }
  box.innerHTML = html;
  box.querySelectorAll(".title-zh[data-url]").forEach(el =>
    el.addEventListener("click", () => window.open(el.dataset.url, "_blank")));
  requestAnimationFrame(() => {
    document.querySelectorAll(".card").forEach((c, i) => setTimeout(() => c.classList.add("in"), 45 * i));
  });
}

/* ---------- autocomplete over lanes + trending ---------- */
let AC_ITEMS = [];
function buildAC() {
  AC_ITEMS = LANES.map(l => ({ q: l.zh, en: l.en })).concat(TRENDING.map(t => ({ q: t.q, en: "" })));
}
let TRENDING = [];

function refreshTrending() {
  fetch("/api/search?q=" + encodeURIComponent(LANES[0].zh)).then(r => r.json()).then(d => {
    TRENDING = d.trending || [];
    const tc = document.getElementById("trendingChips");
    const list = TRENDING.length ? TRENDING : [{ q: "上海 签证 政策", c: 0 }, { q: "移动支付 外国游客", c: 0 }];
    tc.innerHTML = list.slice(0, 6).map(t =>
      `<span class="chip" data-q="${esc(t.q)}">🔥 ${esc(t.q)}</span>`).join("");
    buildAC();
  }).catch(() => {});
}

const acEl = () => document.getElementById("ac");
function closeAC() { acEl().classList.remove("open"); }

document.addEventListener("DOMContentLoaded", () => {
  // lane chips
  document.getElementById("laneChips").innerHTML = LANES.map(l =>
    `<span class="chip" data-q="${esc(l.zh)}"><span class="dot ${l.dot}"></span>${esc(l.zh)} <em style="color:var(--dim);font-style:normal;font-size:12px">${esc(l.en)}</em></span>`).join("");
  buildAC();
  refreshTrending();
  document.getElementById("laneChips").addEventListener("click", e => {
    const c = e.target.closest("[data-q]"); if (c) run(c.dataset.q); });
  document.getElementById("trendingChips").addEventListener("click", e => {
    const c = e.target.closest("[data-q]"); if (c) run(c.dataset.q); });

  const input = document.getElementById("q");
  input.addEventListener("input", () => {
    const v = input.value.trim().toLowerCase();
    const ac = acEl();
    if (!v) { closeAC(); return; }
    const matches = AC_ITEMS.filter(x => x.q.toLowerCase().includes(v) || (x.en && x.en.toLowerCase().includes(v))).slice(0, 6);
    if (!matches.length) { closeAC(); return; }
    ac.innerHTML = matches.map(m => `<div data-q="${esc(m.q)}"><span>${esc(m.q)}</span><span class="en">${esc(m.en)}</span></div>`).join("");
    ac.querySelectorAll("[data-q]").forEach(el => el.addEventListener("click", () => { run(el.dataset.q); closeAC(); }));
    ac.classList.add("open");
  });
  input.addEventListener("keydown", e => { if (e.key === "Escape") closeAC(); });
  document.addEventListener("click", e => { if (!e.target.closest(".searchbar")) closeAC(); });

  fetch("/api/status").then(r => r.json()).then(s => {
    document.getElementById("status").textContent =
      `${s.counts.docs} docs · ${s.counts.chunks} chunks indexed · ` +
      `MT:${s.translate_provider} LLM:${s.llm_provider} LIVE:${s.live_crawl_enabled ? "on" : "off"}`;
  }).catch(() => {});
});
