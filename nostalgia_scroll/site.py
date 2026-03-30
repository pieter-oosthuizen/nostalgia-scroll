from __future__ import annotations

import html
import json
import mimetypes
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nostalgia_scroll.models import Message


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
.pill{border:1px solid var(--stroke);background:color-mix(in oklab, Canvas 92%, CanvasText 8%);border-radius:999px;padding:6px 10px;font-size:12px;text-decoration:none;white-space:nowrap}
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
  const elSubtitle = document.getElementById("subtitle");
  const selC0 = document.getElementById("color0");
  const selC1 = document.getElementById("color1");
  const swC0 = document.getElementById("swatch0");
  const swC1 = document.getElementById("swatch1");
  const elP0 = document.getElementById("p0Name");
  const elP1 = document.getElementById("p1Name");
  const elOverlay = document.getElementById("overlay");
  const elOverlayImg = document.getElementById("overlayImg");

  const PALETTE = [
    ["Emerald", "#2b7"], ["Blue", "#48f"], ["Purple", "#a5f"], ["Orange", "#f84"], ["Red", "#f44"],
    ["Teal", "#0aa"], ["Pink", "#f6a"], ["Gold", "#fb0"], ["Indigo", "#55f"], ["Slate", "#667085"]
  ];

  function setVar(name, value){ document.documentElement.style.setProperty(name, value); }
  function loadPrefs(){
    const a = localStorage.getItem("wa_color0");
    const b = localStorage.getItem("wa_color1");
    return { c0: a || PALETTE[0][1], c1: b || PALETTE[1][1] };
  }
  function savePrefs(c0,c1){ localStorage.setItem("wa_color0", c0); localStorage.setItem("wa_color1", c1); }
  function populateColorSelect(sel, initial){
    sel.innerHTML = "";
    for (const [label, hex] of PALETTE){
      const opt = document.createElement("option");
      opt.value = hex;
      opt.textContent = label;
      opt.style.color = hex;
      sel.appendChild(opt);
    }
    sel.value = initial;
  }

  function openOverlay(src, alt){
    if (!elOverlay || !elOverlayImg) return;
    elOverlayImg.src = src;
    elOverlayImg.alt = alt || "image";
    elOverlay.classList.add("open");
  }
  function closeOverlay(){
    if (!elOverlay || !elOverlayImg) return;
    elOverlay.classList.remove("open");
    setTimeout(() => { elOverlayImg.src = ""; }, 0);
  }

  function boot(){
    const metaRaw = (document.getElementById("meta")?.textContent || "").trim();
    const meta = metaRaw ? JSON.parse(metaRaw) : null;
    if (!meta) return;

    elSubtitle.textContent = `${meta.total_messages.toLocaleString()} messages • ${meta.months.length} months`;
    elP0.textContent = meta.participants[0] || "Participant 1";
    elP1.textContent = meta.participants[1] || "Participant 2";

    const prefs = loadPrefs();
    populateColorSelect(selC0, prefs.c0);
    populateColorSelect(selC1, prefs.c1);
    setVar("--c0", prefs.c0);
    setVar("--c1", prefs.c1);
    if (swC0) swC0.style.background = prefs.c0;
    if (swC1) swC1.style.background = prefs.c1;

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

    if (elOverlay) elOverlay.addEventListener("click", closeOverlay);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && elOverlay && elOverlay.classList.contains("open")) closeOverlay();
    });

    document.querySelectorAll("img[data-fullscreen='1']").forEach((img) => {
      img.addEventListener("click", (e) => {
        e.preventDefault();
        openOverlay(img.getAttribute("src"), img.getAttribute("alt") || "image");
      });
    });
  }

  boot();
})();
"""
    _write_text(site_dir / "assets" / "app.js", js.strip() + "\n")


def render_index(*, site_title: str, subtitle: str, meta: dict, nav_html: str, body_html: str) -> str:
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
          <div class="settings">
            <label><span class="swatch" id="swatch0"></span><span id="p0Name">P0</span><select id="color0"></select></label>
            <label><span class="swatch" id="swatch1"></span><span id="p1Name">P1</span><select id="color1"></select></label>
          </div>
        </div>
        <div class="section">{nav_html}</div>
      </nav>
      <main>
        <div class="topbar">
          <div class="title">
            <strong>Chat timeline</strong>
            <span>Use the month list to jump.</span>
          </div>
        </div>
        <div class="timeline">{body_html}</div>
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
    media_zip_path: Path | None = None,
) -> Path:
    site_dir = output_dir / "site"
    write_assets(site_dir)

    buckets = group_by_month(messages)
    month_keys = list(buckets.keys())
    if not month_keys:
        meta = {"participants": [], "months": [], "total_messages": 0}
        index_html = render_index(site_title=title, subtitle=subtitle, meta=meta, nav_html="", body_html="")
        _write_text(site_dir / "index.html", index_html)
        return site_dir / "index.html"

    counts: dict[str, int] = {}
    for m in messages:
        if m.system:
            continue
        if not m.sender:
            continue
        counts[m.sender] = counts.get(m.sender, 0) + 1
    participants = [s for s, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:2]]
    if len(participants) < 2:
        seen = []
        for m in messages:
            if m.sender and m.sender not in seen:
                seen.append(m.sender)
            if len(seen) == 2:
                break
        participants = (participants + seen)[:2]

    months = [mk.ym for mk in month_keys]
    meta = {"participants": participants, "months": months, "total_messages": len(messages)}

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
        dst = media_dir / name
        dst.parent.mkdir(parents=True, exist_ok=True)

        # 1) Extracted folder mode
        if media_source_dir:
            src = media_source_dir / name
            if src.exists() and src.is_file():
                if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                    shutil.copyfile(src, dst)
                return f"media/{name}"

        # 2) ZIP mode (search for a member with this basename)
        if media_zip_path and media_zip_path.exists() and media_zip_path.is_file():
            try:
                with zipfile.ZipFile(media_zip_path, "r") as zf:
                    target = None
                    for member in zf.namelist():
                        if Path(member).name == name:
                            target = member
                            break
                    if target is None:
                        return None
                    data = zf.read(target)
                    if not dst.exists() or dst.stat().st_size != len(data):
                        dst.write_bytes(data)
                    return f"media/{name}"
            except zipfile.BadZipFile:
                return None

        return None

    # Build nav + full HTML body
    by_year: dict[int, list[MonthKey]] = {}
    for mk in month_keys:
        by_year.setdefault(mk.year, []).append(mk)
    nav_parts: list[str] = []
    for y, mks in by_year.items():
        nav_parts.append(f'<div class="year">{y}</div><ul>')
        for mk in mks:
            nav_parts.append(f'<li><a href="#m-{mk.ym.replace("-", "")}">{mk.label}</a></li>')
        nav_parts.append("</ul>")
    nav_html = "\n".join(nav_parts)

    body_parts: list[str] = []
    for mk in month_keys:
        month_id = f"m-{mk.ym.replace('-', '')}"
        month_msgs = buckets[mk]
        body_parts.append(f'<section class="month" id="{month_id}">')
        body_parts.append(
            f'<div class="monthHeader"><strong>{_escape(mk.label)}</strong><span>{len(month_msgs):,} messages</span></div>'
        )
        body_parts.append('<div class="messages">')

        current_day: str | None = None
        for m in month_msgs:
            dt = _dt_local(m.ts_ms)
            day = dt.strftime("%Y-%m-%d (%a)")
            if day != current_day:
                body_parts.append(f'<div class="day">{_escape(day)}</div>')
                current_day = day

            sender = m.sender or ("System" if m.system else "Unknown")
            p = 0
            if participants and sender == participants[1]:
                p = 1
            elif participants and sender != participants[0]:
                p = 1
            row_class = "row left" if p == 0 else "row right"
            bubble_class = "bubble p0" if p == 0 else "bubble p1"
            ts = dt.strftime("%H:%M")

            cleaned, att_names = extract_attachments(m.text)
            media_bits: list[str] = []
            for nm in att_names:
                rel = copy_media(nm)
                kind = classify(nm)
                if kind == "image" and rel:
                    media_bits.append(
                        f'<img data-fullscreen="1" src="{_escape(rel)}" alt="{_escape(nm)}" loading="lazy" />'
                    )
                elif rel:
                    media_bits.append(f'<a href="{_escape(rel)}" target="_blank" rel="noreferrer">{_escape(nm)}</a>')
                else:
                    media_bits.append(f'<span style="color:var(--muted);font-size:12px">{_escape(nm)}</span>')

            media_html = f'<div class="media">{"".join(media_bits)}</div>' if media_bits else ""

            body_parts.append(
                f'<div class="{row_class}"><div class="ts">{_escape(ts)} • {_escape(sender)}</div><div class="{bubble_class}"><div class="text">{_escape(cleaned)}</div>{media_html}</div></div>'
            )

        body_parts.append("</div></section>")

    body_html = "\n".join(body_parts)

    index_html = render_index(site_title=title, subtitle=subtitle, meta=meta, nav_html=nav_html, body_html=body_html)
    _write_text(site_dir / "index.html", index_html)
    return site_dir / "index.html"

