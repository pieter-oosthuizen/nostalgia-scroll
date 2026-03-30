from __future__ import annotations

import html
import json
import mimetypes
import re
import shutil
import subprocess
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
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Small CSS that complements Tailwind (participant bubble colors)
    extra_css = """
:root { --c0: #2b7; --c1: #48f; }
.bubble-p0 { background-color: color-mix(in oklab, var(--c0) 16%, white 84%); }
.bubble-p1 { background-color: color-mix(in oklab, var(--c1) 16%, white 84%); }
.msg-row[data-side="left"] { align-self: flex-start; }
.msg-row[data-side="right"] { align-self: flex-end; }
@media (prefers-color-scheme: dark) {
  .bubble-p0 { background-color: color-mix(in oklab, var(--c0) 22%, rgb(17 24 39) 78%); }
  .bubble-p1 { background-color: color-mix(in oklab, var(--c1) 22%, rgb(17 24 39) 78%); }
}
"""
    _write_text(assets_dir / "app.css", extra_css.strip() + "\n")

    js = r"""
(function(){
  const elSubtitle = document.getElementById("subtitle");
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

  function applySides(swapped){
    document.querySelectorAll(".msg-row[data-p]").forEach((el) => {
      const pRaw = el.getAttribute("data-p");
      const p = pRaw === "1" ? 1 : 0;
      const sideP = swapped ? (p === 0 ? 1 : 0) : p;
      el.setAttribute("data-side", sideP === 0 ? "left" : "right");
    });
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

    let swapped = loadSwapSides();
    applySides(swapped);
    if (btnSwitchSides){
      btnSwitchSides.addEventListener("click", () => {
        swapped = !swapped;
        saveSwapSides(swapped);
        applySides(swapped);
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
    <link rel="stylesheet" href="assets/tailwind.css" />
    <link rel="stylesheet" href="assets/app.css" />
  </head>
  <body class="bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <div class="min-h-screen grid grid-cols-1 md:grid-cols-[280px_1fr]">
      <nav class="md:sticky md:top-0 md:h-screen overflow-auto border-b md:border-b-0 md:border-r border-slate-200/70 dark:border-slate-800/70 bg-slate-50/80 dark:bg-slate-900/30 backdrop-blur">
        <header class="px-3 py-3 border-b border-slate-200/70 dark:border-slate-800/70">
          <div class="text-sm font-semibold">{_escape(site_title)}</div>
          <div id="subtitle" class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{_escape(subtitle)}</div>
        </header>
        <div class="px-3 py-3">
          <button id="switchSides" type="button" class="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-950/40 px-3 py-2 text-xs font-medium hover:bg-white dark:hover:bg-slate-950/60">
            Switch User Sides
          </button>
          <div class="h-2"></div>
          <div class="flex flex-wrap items-center gap-2">
            <label class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span id="swatch0" class="inline-block w-3 h-3 rounded border border-slate-300 dark:border-slate-700"></span>
              <span id="p0Name">P0</span>
              <select id="color0" class="text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-950/40 px-2 py-1"></select>
            </label>
            <label class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span id="swatch1" class="inline-block w-3 h-3 rounded border border-slate-300 dark:border-slate-700"></span>
              <span id="p1Name">P1</span>
              <select id="color1" class="text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-950/40 px-2 py-1"></select>
            </label>
          </div>
        </div>
        <div class="px-3 pb-5 text-sm">{nav_html}</div>
      </nav>
      <main class="px-4 py-4 md:px-6 md:py-6 max-w-5xl mx-auto w-full">
        <div class="flex items-center justify-between gap-3 mb-4">
          <div>
            <div class="text-sm font-semibold">Chat timeline</div>
            <div class="text-xs text-slate-500 dark:text-slate-400">Use the month list to jump.</div>
          </div>
        </div>
        <div class="flex flex-col gap-6">{body_html}</div>
      </main>
    </div>

    <div id="overlay" class="fixed inset-0 hidden items-center justify-center bg-black/80 p-6 z-50">
      <img id="overlayImg" alt="" class="max-w-[min(95vw,1200px)] max-h-[95vh] rounded-xl border border-white/15 shadow-2xl cursor-zoom-out bg-slate-900" />
      <div class="absolute bottom-3 left-0 right-0 text-center text-xs text-white/80">Click to close • Esc</div>
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
        nav_parts.append(f'<div class="mt-4 mb-1 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">{y}</div><ul class="space-y-1">')
        for mk in mks:
            nav_parts.append(
                f'<li><a class="block rounded-lg px-2 py-1 hover:bg-slate-200/60 dark:hover:bg-slate-800/50" href="#m-{mk.ym.replace("-", "")}">{mk.label}</a></li>'
            )
        nav_parts.append("</ul>")
    nav_html = "\n".join(nav_parts)

    body_parts: list[str] = []
    for mk in month_keys:
        month_id = f"m-{mk.ym.replace('-', '')}"
        month_msgs = buckets[mk]
        body_parts.append(f'<section class="scroll-mt-3" id="{month_id}">')
        body_parts.append(
            f'<div class="flex items-baseline justify-between gap-3 mb-3"><div class="text-sm font-semibold">{_escape(mk.label)}</div><div class="text-xs text-slate-500 dark:text-slate-400">{len(month_msgs):,} messages</div></div>'
        )
        body_parts.append('<div class="flex flex-col gap-2">')

        current_day: str | None = None
        for m in month_msgs:
            dt = _dt_local(m.ts_ms)
            day = dt.strftime("%Y-%m-%d (%a)")
            if day != current_day:
                body_parts.append(f'<div class="mt-4 pt-2 border-t border-dashed border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400">{_escape(day)}</div>')
                current_day = day

            sender = m.sender or ("System" if m.system else "Unknown")
            p = 0
            if participants and sender == participants[1]:
                p = 1
            elif participants and sender != participants[0]:
                p = 1
            row_class = "row left" if p == 0 else "row right"
            bubble_class = "bubble-p0" if p == 0 else "bubble-p1"
            ts = dt.strftime("%H:%M")

            cleaned, att_names = extract_attachments(m.text)
            media_bits: list[str] = []
            for nm in att_names:
                rel = copy_media(nm)
                kind = classify(nm)
                if kind == "image" and rel:
                    media_bits.append(
                        f'<img class="mt-2 max-w-[300px] max-h-[300px] w-auto h-auto object-contain rounded-xl border border-slate-200 dark:border-slate-800 cursor-zoom-in" data-fullscreen="1" src="{_escape(rel)}" alt="{_escape(nm)}" loading="lazy" />'
                    )
                elif rel:
                    media_bits.append(
                        f'<a class="mt-2 text-xs text-slate-500 dark:text-slate-400 underline" href="{_escape(rel)}" target="_blank" rel="noreferrer">{_escape(nm)}</a>'
                    )
                else:
                    media_bits.append(
                        f'<div class="mt-2 text-xs text-slate-500 dark:text-slate-400">{_escape(nm)}</div>'
                    )

            media_html = f'{"".join(media_bits)}' if media_bits else ""

            body_parts.append(
                f'<div class="msg-row flex flex-col gap-1 max-w-[min(720px,92%)]" data-p="{p}" data-side="{"left" if p == 0 else "right"}">'
                f'<div class="text-[11px] text-slate-500 dark:text-slate-400 tabular-nums">{_escape(ts)} • {_escape(sender)}</div>'
                f'<div class="rounded-2xl border border-slate-200 dark:border-slate-800 px-3 py-2 {bubble_class}">'
                f'<div class="whitespace-pre-wrap break-words text-[13px] leading-snug">{_escape(cleaned)}</div>'
                f'{media_html}'
                f"</div></div>"
            )

        body_parts.append("</div></section>")

    body_html = "\n".join(body_parts)

    index_html = render_index(site_title=title, subtitle=subtitle, meta=meta, nav_html=nav_html, body_html=body_html)
    _write_text(site_dir / "index.html", index_html)

    # Build Tailwind CSS (compiled, offline, fast)
    input_css = Path(__file__).with_name("tailwind.input.css")
    out_css = site_dir / "assets" / "tailwind.css"
    index_path = site_dir / "index.html"
    try:
        subprocess.run(
            [
                "npx",
                "tailwindcss",
                "-i",
                str(input_css),
                "-o",
                str(out_css),
                "--minify",
                "--content",
                str(index_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Tailwind build requires Node.js + npm (for `npx tailwindcss`). "
            "Install Node, then run `npm install` in this repo."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Tailwind build failed:\n{e.stdout}") from e

    return site_dir / "index.html"

