from __future__ import annotations

import html
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from whatsapp_viz.models import Message


@dataclass(frozen=True, slots=True)
class MonthKey:
    year: int
    month: int

    @property
    def ym(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def _dt_local(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000.0)


def _escape(s: str) -> str:
    return html.escape(s, quote=False)


def group_by_month(messages: list[Message]) -> dict[MonthKey, list[Message]]:
    buckets: dict[MonthKey, list[Message]] = {}
    for m in messages:
        dt = _dt_local(m.ts_ms)
        key = MonthKey(dt.year, dt.month)
        buckets.setdefault(key, []).append(m)
    # Ensure stable sort inside each bucket
    for k in list(buckets.keys()):
        buckets[k].sort(key=lambda mm: (mm.ts_ms, mm.id))
    return dict(sorted(buckets.items(), key=lambda kv: (kv[0].year, kv[0].month)))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_assets(site_dir: Path) -> None:
    css = """
:root{color-scheme:light dark;--bg:Canvas;--fg:CanvasText;--muted:color-mix(in oklab, CanvasText 55%, Canvas 45%);--stroke:color-mix(in oklab, CanvasText 22%, Canvas 78%);--panel:color-mix(in oklab, Canvas 88%, CanvasText 12%);--c0:#2b7;--c1:#48f;}
html,body{height:100%;margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
a{color:inherit}
.layout{display:grid;grid-template-columns:280px 1fr;min-height:100vh}
nav{position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--stroke);background:var(--panel)}
nav header{padding:12px 12px 10px;border-bottom:1px solid var(--stroke)}
nav header strong{display:block;font-size:13px}
nav header span{display:block;color:var(--muted);font-size:12px;margin-top:2px}
nav .section{padding:10px 12px}
nav .year{margin:10px 0 6px;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
nav ul{list-style:none;padding:0;margin:0}
nav li{margin:2px 0}
nav a{display:block;padding:7px 8px;border-radius:10px;text-decoration:none}
nav a:hover{background:color-mix(in oklab, CanvasText 6%, Canvas 94%)}
main{padding:14px 18px 40px;max-width:980px;margin:0 auto}
.topbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}
.topbar .title{display:flex;flex-direction:column;gap:2px}
.topbar .title strong{font-size:14px}
.topbar .title span{color:var(--muted);font-size:12px}
.pill{border:1px solid var(--stroke);background:color-mix(in oklab, Canvas 92%, CanvasText 8%);border-radius:999px;padding:6px 10px;font-size:12px;text-decoration:none;white-space:nowrap;cursor:pointer}
.settings{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.settings label{font-size:12px;color:var(--muted);display:flex;gap:8px;align-items:center}
.swatch{width:12px;height:12px;border-radius:4px;border:1px solid var(--stroke);background:var(--fg);display:inline-block}
.settings select{border:1px solid var(--stroke);background:color-mix(in oklab, Canvas 92%, CanvasText 8%);color:var(--fg);border-radius:10px;padding:6px 8px}
.timeline{display:flex;flex-direction:column;gap:18px}
.month{scroll-margin-top:10px}
.monthHeader{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:8px 0 10px}
.monthHeader strong{font-size:13px}
.monthHeader span{font-size:12px;color:var(--muted)}
.messages{display:flex;flex-direction:column;gap:8px}
.day{margin:14px 0 6px;padding-top:6px;border-top:1px dashed var(--stroke);color:var(--muted);font-size:12px}
.row{display:flex;flex-direction:column;gap:2px;max-width:min(720px, 92%)}
.row.left{align-self:flex-start}
.row.right{align-self:flex-end}
.ts{font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px}
.bubble{border:1px solid var(--stroke);border-radius:14px;padding:10px 12px;background:color-mix(in oklab, var(--c1) 16%, Canvas 84%)}
.bubble.p0{background:color-mix(in oklab, var(--c0) 16%, Canvas 84%)}
.bubble.p1{background:color-mix(in oklab, var(--c1) 16%, Canvas 84%)}
.media{margin-top:8px;display:flex;flex-direction:column;gap:8px}
.media img{max-width:300px;max-height:300px;width:auto;height:auto;object-fit:contain;border-radius:12px;border:1px solid var(--stroke);display:block;cursor:zoom-in}
.media a{font-size:12px;color:var(--muted)}
.overlay{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.75);padding:24px;z-index:9999}
.overlay.open{display:flex}
.overlay img{max-width:min(95vw, 1200px);max-height:95vh;width:auto;height:auto;object-fit:contain;border-radius:14px;border:1px solid rgba(255,255,255,.18);box-shadow:0 18px 60px rgba(0,0,0,.45);cursor:zoom-out;background:color-mix(in oklab, Canvas 35%, black 65%)}
.overlay .hint{position:absolute;bottom:14px;left:0;right:0;text-align:center;color:rgba(255,255,255,.85);font-size:12px}
.meta{display:flex;gap:8px;align-items:baseline;margin-bottom:6px}
.sender{font-weight:600;font-size:12px}
.flags{color:var(--muted);font-size:12px}
.text{white-space:pre-wrap;word-wrap:break-word;font-size:13px;line-height:1.35}
.pager{display:flex;gap:10px;margin:16px 0 6px}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{position:relative;height:auto;border-right:none;border-bottom:1px solid var(--stroke)}}
"""
    _write_text(site_dir / "assets" / "style.css", css.strip() + "\n")

    js = r"""
(function(){
  const state = {
    meta: null,
    loaded: new Set(),
    loading: new Set(),
    monthOrder: [],
    nextIdx: 0,
    swapped: false
  };

  const elSubtitle = document.getElementById("subtitle");
  const elNav = document.getElementById("navMonths");
  const elTimeline = document.getElementById("timeline");
  const elSentinel = document.getElementById("sentinel");
  const selC0 = document.getElementById("color0");
  const selC1 = document.getElementById("color1");
  const swC0 = document.getElementById("swatch0");
  const swC1 = document.getElementById("swatch1");
  const elP0 = document.getElementById("p0Name");
  const elP1 = document.getElementById("p1Name");
  const btnSwitchSides = document.getElementById("switchSides");
  const elOverlay = document.getElementById("overlay");
  const elOverlayImg = document.getElementById("overlayImg");

  const PALETTE = [
    ["Emerald", "#2b7"], ["Blue", "#48f"], ["Purple", "#a5f"], ["Orange", "#f84"], ["Red", "#f44"],
    ["Teal", "#0aa"], ["Pink", "#f6a"], ["Gold", "#fb0"], ["Indigo", "#55f"], ["Slate", "#667085"]
  ];

  function setVar(name, value){ document.documentElement.style.setProperty(name, value); }
  function loadSwapSides(){ return localStorage.getItem("wa_swap_sides") === "1"; }
  function saveSwapSides(v){ localStorage.setItem("wa_swap_sides", v ? "1" : "0"); }

  function loadPrefs(){
    const a = localStorage.getItem("wa_color0");
    const b = localStorage.getItem("wa_color1");
    return { c0: a || PALETTE[0][1], c1: b || PALETTE[1][1] };
  }
  function savePrefs(c0,c1){
    localStorage.setItem("wa_color0", c0);
    localStorage.setItem("wa_color1", c1);
  }

  function populateColorSelect(sel, initial){
    sel.innerHTML = "";
    for (const [label, hex] of PALETTE){
      const opt = document.createElement("option");
      opt.value = hex;
      opt.textContent = label;
      // Some browsers ignore styling <option>, but where supported this helps.
      opt.style.color = hex;
      sel.appendChild(opt);
    }
    sel.value = initial;
  }

  function renderNav(meta){
    // meta.months is ["YYYY-MM", ...]
    const months = meta.months;
    const byYear = new Map();
    for (const ym of months){
      const y = ym.slice(0,4);
      if (!byYear.has(y)) byYear.set(y, []);
      byYear.get(y).push(ym);
    }
    elNav.innerHTML = "";
    for (const [y, list] of byYear.entries()){
      const yDiv = document.createElement("div");
      yDiv.className = "year";
      yDiv.textContent = y;
      elNav.appendChild(yDiv);
      const ul = document.createElement("ul");
      for (const ym of list){
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = "#m-" + ym.replace("-","");
        a.textContent = ym;
        a.addEventListener("click", async (e) => {
          e.preventDefault();
          await ensureMonthLoaded(ym);
          const el = document.getElementById("m-" + ym.replace("-",""));
          if (el) el.scrollIntoView({behavior:"smooth", block:"start"});
        });
        li.appendChild(a);
        ul.appendChild(li);
      }
      elNav.appendChild(ul);
    }
  }

  function monthScriptSrc(ym){ return "months/" + ym + ".js"; }

  function loadMonthScript(ym){
    return new Promise((resolve, reject) => {
      if (state.loaded.has(ym)) return resolve();
      if (state.loading.has(ym)) return resolve(); // will be resolved by later check
      state.loading.add(ym);
      const s = document.createElement("script");
      s.src = monthScriptSrc(ym);
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed to load " + s.src));
      document.head.appendChild(s);
    });
  }

  function fmtDay(ts){
    const d = new Date(ts);
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,"0");
    const dd = String(d.getDate()).padStart(2,"0");
    const wk = d.toLocaleDateString(undefined, { weekday: "short" });
    return `${y}-${m}-${dd} (${wk})`;
  }
  function fmtTime(ts){
    const d = new Date(ts);
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  function renderMonth(ym, payload){
    if (state.loaded.has(ym)) return;
    state.loaded.add(ym);
    state.loading.delete(ym);

    const monthId = "m-" + ym.replace("-","");
    const monthEl = document.createElement("section");
    monthEl.className = "month";
    monthEl.id = monthId;

    const header = document.createElement("div");
    header.className = "monthHeader";
    const strong = document.createElement("strong");
    strong.textContent = ym;
    const span = document.createElement("span");
    span.textContent = `${payload.messages.length.toLocaleString()} messages`;
    header.appendChild(strong);
    header.appendChild(span);
    monthEl.appendChild(header);

    const msgsEl = document.createElement("div");
    msgsEl.className = "messages";

    let currentDay = null;
    for (const msg of payload.messages){
      const day = fmtDay(msg.ts);
      if (day !== currentDay){
        const dayEl = document.createElement("div");
        dayEl.className = "day";
        dayEl.textContent = day;
        msgsEl.appendChild(dayEl);
        currentDay = day;
      }

      const row = document.createElement("div");
      const sideP = state.swapped ? (msg.p === 0 ? 1 : 0) : msg.p;
      row.className = "row " + (sideP === 0 ? "left" : "right");

      const ts = document.createElement("div");
      ts.className = "ts";
      ts.textContent = `${fmtTime(msg.ts)} • ${msg.sender}`;
      row.appendChild(ts);

      const bubble = document.createElement("div");
      bubble.className = "bubble " + (msg.p === 0 ? "p0" : "p1");

      const text = document.createElement("div");
      text.className = "text";
      text.textContent = msg.text;
      bubble.appendChild(text);

      if (msg.media && msg.media.length){
        const mediaWrap = document.createElement("div");
        mediaWrap.className = "media";
        for (const it of msg.media){
          if (it.kind === "image"){
            const img = document.createElement("img");
            img.src = it.src;
            img.loading = "lazy";
            img.alt = it.name || "image";
            img.addEventListener("click", (e) => {
              e.preventDefault();
              openOverlay(img.src, img.alt);
            });
            mediaWrap.appendChild(img);
          } else {
            const a = document.createElement("a");
            a.href = it.src;
            a.textContent = it.name || it.src;
            a.target = "_blank";
            a.rel = "noreferrer";
            mediaWrap.appendChild(a);
          }
        }
        bubble.appendChild(mediaWrap);
      }

      row.appendChild(bubble);
      msgsEl.appendChild(row);
    }

    monthEl.appendChild(msgsEl);
    elTimeline.appendChild(monthEl);
  }

  async function ensureMonthLoaded(ym){
    if (state.loaded.has(ym)) return;
    await loadMonthScript(ym);
    // month scripts call window.__waMonthLoaded(ym, payload)
  }

  async function loadNext(){
    if (state.nextIdx >= state.monthOrder.length) return;
    const ym = state.monthOrder[state.nextIdx];
    state.nextIdx += 1;
    await ensureMonthLoaded(ym);
  }

  function setupInfiniteScroll(){
    const io = new IntersectionObserver(async (entries) => {
      for (const e of entries){
        if (e.isIntersecting){
          // Load a few ahead for smoother scroll
          await loadNext();
          await loadNext();
        }
      }
    }, { root: null, threshold: 0.1 });
    io.observe(elSentinel);
  }

  window.__waMonthLoaded = (ym, payload) => {
    renderMonth(ym, payload);
  };

  function openOverlay(src, alt){
    if (!elOverlay || !elOverlayImg) return;
    elOverlayImg.src = src;
    elOverlayImg.alt = alt || "image";
    elOverlay.classList.add("open");
  }
  function closeOverlay(){
    if (!elOverlay || !elOverlayImg) return;
    elOverlay.classList.remove("open");
    // Release reference after a tick to avoid flicker on rapid reopen
    setTimeout(() => { elOverlayImg.src = ""; }, 0);
  }

  function boot(){
    const metaRaw = (document.getElementById("meta")?.textContent || "").trim();
    state.meta = metaRaw ? JSON.parse(metaRaw) : null;
    if (!state.meta) return;

    elSubtitle.textContent = `${state.meta.total_messages.toLocaleString()} messages • ${state.meta.months.length} months`;
    elP0.textContent = state.meta.participants[0] || "Participant 1";
    elP1.textContent = state.meta.participants[1] || "Participant 2";

    renderNav(state.meta);
    state.monthOrder = state.meta.months;

    const prefs = loadPrefs();
    populateColorSelect(selC0, prefs.c0);
    populateColorSelect(selC1, prefs.c1);
    setVar("--c0", prefs.c0);
    setVar("--c1", prefs.c1);
    if (swC0) swC0.style.background = prefs.c0;
    if (swC1) swC1.style.background = prefs.c1;

    state.swapped = loadSwapSides();
    if (btnSwitchSides){
      btnSwitchSides.addEventListener("click", () => {
        state.swapped = !state.swapped;
        saveSwapSides(state.swapped);
        // Apply to already-rendered months
        document.querySelectorAll(".row").forEach((row) => {
          const bubble = row.querySelector(".bubble");
          if (!bubble) return;
          const isP0 = bubble.classList.contains("p0");
          const p = isP0 ? 0 : 1;
          const sideP = state.swapped ? (p === 0 ? 1 : 0) : p;
          row.classList.toggle("left", sideP === 0);
          row.classList.toggle("right", sideP === 1);
        });
      });
    }

    function onColorChange(){
      const c0 = selC0.value;
      const c1 = selC1.value;
      setVar("--c0", c0);
      setVar("--c1", c1);
      if (swC0) swC0.style.background = c0;
      if (swC1) swC1.style.background = c1;
      savePrefs(c0, c1);
    }
    selC0.addEventListener("change", onColorChange);
    selC1.addEventListener("change", onColorChange);

    // Load first couple of months immediately
    loadNext().then(() => loadNext());
    setupInfiniteScroll();

    if (elOverlay){
      elOverlay.addEventListener("click", closeOverlay);
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && elOverlay && elOverlay.classList.contains("open")) closeOverlay();
    });
  }

  boot();
})();
"""
    _write_text(site_dir / "assets" / "app.js", js.strip() + "\n")


def render_index(*, site_title: str, subtitle: str, meta: dict) -> str:
    meta_json = json.dumps(meta, ensure_ascii=False)
    body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape(site_title)}</title>
    <link rel="stylesheet" href="assets/style.css" />
  </head>
  <body>
    <div class="layout">
      <nav>
        <header>
          <strong>{_escape(site_title)}</strong>
          <span id="subtitle">{_escape(subtitle)}</span>
        </header>
        <div class="section">
          <button id="switchSides" type="button" class="pill" style="width:100%;text-align:center;margin-bottom:10px">Switch User Sides</button>
          <div class="settings">
            <label><span class="swatch" id="swatch0"></span><span id="p0Name">P0</span><select id="color0"></select></label>
            <label><span class="swatch" id="swatch1"></span><span id="p1Name">P1</span><select id="color1"></select></label>
          </div>
        </div>
        <div class="section" id="navMonths"></div>
      </nav>
      <main>
        <div class="topbar">
          <div class="title">
            <strong>Chat timeline</strong>
            <span>Scroll to load more. Use the month list to jump.</span>
          </div>
        </div>
        <div class="timeline" id="timeline"></div>
        <div id="sentinel" style="height: 1px;"></div>
      </main>
    </div>

    <div class="overlay" id="overlay" aria-hidden="true">
      <img id="overlayImg" alt="" />
      <div class="hint">Click to close • Esc</div>
    </div>

    <script id="meta" type="application/json">{_escape(meta_json)}</script>
    <script src="assets/app.js"></script>
  </body>
</html>
"""
    return body


def build_site(
    *,
    output_dir: Path,
    messages: list[Message],
    title: str = "WhatsApp chat",
    subtitle: str = "Generated locally",
    media_source_dir: Path | None = None,
) -> Path:
    site_dir = output_dir / "site"
    write_assets(site_dir)

    buckets = group_by_month(messages)
    month_keys = list(buckets.keys())
    if not month_keys:
        meta = {"participants": [], "months": [], "total_messages": 0}
        index_html = render_index(site_title=title, subtitle=subtitle, meta=meta)
        _write_text(site_dir / "index.html", index_html)
        return site_dir / "index.html"

    # Determine the two participants (most common non-system senders)
    counts: dict[str, int] = {}
    for m in messages:
        if m.system:
            continue
        if not m.sender:
            continue
        counts[m.sender] = counts.get(m.sender, 0) + 1
    participants = [s for s, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:2]]
    if len(participants) < 2:
        # Fallback to unique senders
        seen = []
        for m in messages:
            if m.sender and m.sender not in seen:
                seen.append(m.sender)
            if len(seen) == 2:
                break
        participants = (participants + seen)[:2]

    months = [mk.ym for mk in month_keys]
    meta = {
        "participants": participants,
        "months": months,
        "total_messages": len(messages),
    }

    media_dir = site_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    attach_re = re.compile(r"<attached:\s*([^>]+)>")

    def extract_attachments(text: str) -> tuple[str, list[str]]:
        names = [m.group(1).strip() for m in attach_re.finditer(text)]
        cleaned = attach_re.sub("", text).strip()
        return cleaned, names

    def classify(name: str) -> str:
        mt, _ = mimetypes.guess_type(name)
        if mt and mt.startswith("image/"):
            return "image"
        lower = name.lower()
        if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")):
            return "image"
        return "file"

    def copy_media(name: str) -> str | None:
        if not media_source_dir:
            return None
        src = media_source_dir / name
        if not src.exists() or not src.is_file():
            return None
        dst = media_dir / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)
        return f"media/{name}"

    # Write month chunks as JS files (so they can be loaded from file:// without fetch()).
    months_dir = site_dir / "months"
    months_dir.mkdir(parents=True, exist_ok=True)
    for mk in month_keys:
        out_msgs = []
        for m in buckets[mk]:
            sender = m.sender or ("System" if m.system else "Unknown")
            p = 0
            if participants and sender == participants[1]:
                p = 1
            elif participants and sender != participants[0]:
                # Anything not participant[0] becomes "other side"
                p = 1

            cleaned, att_names = extract_attachments(m.text)
            media_items = []
            for nm in att_names:
                rel = copy_media(nm)
                if rel:
                    media_items.append({"kind": classify(nm), "src": rel, "name": nm})
                else:
                    media_items.append({"kind": classify(nm), "src": nm, "name": nm})

            out_msgs.append({"ts": m.ts_ms, "sender": sender, "text": cleaned, "p": p, "media": media_items})
        payload = {"messages": out_msgs}
        js = f"window.__waMonthLoaded && window.__waMonthLoaded({json.dumps(mk.ym)}, {json.dumps(payload, ensure_ascii=False)});"
        _write_text(months_dir / f"{mk.ym}.js", js + "\n")

    index_html = render_index(site_title=title, subtitle=subtitle, meta=meta)
    _write_text(site_dir / "index.html", index_html)

    return site_dir / "index.html"

