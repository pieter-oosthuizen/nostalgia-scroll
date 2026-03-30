from __future__ import annotations

import argparse
import html
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Message:
    id: int
    ts_ms: int
    ts_iso: str
    sender: str | None
    text: str
    has_media: bool
    system: bool


@dataclass(frozen=True, slots=True)
class ZipChatSource:
    zip_path: str
    chat_txt_path: str
    messages: list[Message]


_IOS_LINE_RE = re.compile(
    r"^(?:\[(?P<br_date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<br_time>\d{1,2}:\d{2})(?::(?P<br_sec>\d{2}))?\]\s+|(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2})(?::(?P<sec>\d{2}))?\s*(?P<ampm>[AP]M)?\s*-\s*)(?P<body>.*)$"
)


def discover_ios_export_zip(source_dir: Path) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    zips = sorted(source_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        raise FileNotFoundError(f"No .zip files found in {source_dir}")
    return zips[0]


def discover_ios_chat_txt(source_dir: Path) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    direct = source_dir / "_chat.txt"
    if direct.exists() and direct.is_file():
        return direct
    txts = sorted(source_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txts:
        raise FileNotFoundError(f"No .txt files found in {source_dir}")
    return txts[0]


def _pick_chat_txt_path(zf: zipfile.ZipFile) -> str:
    candidates = [zi.filename for zi in zf.infolist() if zi.filename.lower().endswith(".txt")]
    if not candidates:
        raise FileNotFoundError("No .txt file found inside ZIP (expected WhatsApp chat export text).")
    chatish = [c for c in candidates if "chat" in Path(c).name.lower()]
    if chatish:
        return sorted(chatish, key=len)[0]
    return max(candidates, key=lambda fn: zf.getinfo(fn).file_size)


def _local_tz() -> ZoneInfo:
    try:
        return ZoneInfo(str(datetime.now().astimezone().tzinfo))
    except Exception:
        return ZoneInfo("UTC")


def _parse_ts(date_s: str, time_s: str, sec_s: str | None, ampm: str | None, tz: ZoneInfo) -> datetime:
    sec = sec_s or "00"
    year_token = date_s.split("/")[-1]
    yfmt = "%Y" if len(year_token) == 4 else "%y"
    if ampm:
        s = f"{date_s} {time_s}:{sec} {ampm}"
        try:
            dt = datetime.strptime(s, f"%m/%d/{yfmt} %I:%M:%S %p")
        except ValueError:
            dt = datetime.strptime(s, f"%d/%m/{yfmt} %I:%M:%S %p")
    else:
        s = f"{date_s} {time_s}:{sec}"
        try:
            dt = datetime.strptime(s, f"%m/%d/{yfmt} %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(s, f"%d/%m/{yfmt} %H:%M:%S")
    return dt.replace(tzinfo=tz)


def parse_ios_chat_text(chat_text: str) -> list[Message]:
    tz = _local_tz()
    messages: list[Message] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        messages.append(
            Message(
                id=current["id"],
                ts_ms=current["ts_ms"],
                ts_iso=current["ts_iso"],
                sender=current["sender"],
                text=current["text"].rstrip("\n"),
                has_media=current["has_media"],
                system=current["system"],
            )
        )
        current = None

    lines = chat_text.splitlines()
    msg_id = 0
    for raw in lines:
        m = _IOS_LINE_RE.match(raw)
        if not m:
            if current is not None:
                current["text"] += "\n" + raw
            continue

        flush()
        date_s = m.group("br_date") or m.group("date")
        time_s = m.group("br_time") or m.group("time")
        sec_s = m.group("br_sec") or m.group("sec")
        ampm = m.group("ampm")
        dt = _parse_ts(date_s, time_s, sec_s, ampm, tz=tz)
        ts_ms = int(dt.timestamp() * 1000)
        ts_iso = dt.isoformat()
        body = m.group("body") or ""

        if ": " in body:
            sender, text = body.split(": ", 1)
            system = False
        else:
            sender = None
            text = body
            system = True

        lowered = text.strip().lower()
        has_media = lowered in {"<media omitted>", "image omitted", "video omitted"} or "omitted" in lowered

        current = {
            "id": msg_id,
            "ts_ms": ts_ms,
            "ts_iso": ts_iso,
            "sender": sender,
            "text": text,
            "has_media": has_media,
            "system": system,
        }
        msg_id += 1

    flush()
    messages.sort(key=lambda mm: (mm.ts_ms, mm.id))
    return [
        Message(
            id=i,
            ts_ms=m.ts_ms,
            ts_iso=m.ts_iso,
            sender=m.sender,
            text=m.text,
            has_media=m.has_media,
            system=m.system,
        )
        for i, m in enumerate(messages)
    ]


def parse_ios_export_zip(zip_path: Path) -> ZipChatSource:
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    if zip_path.suffix.lower() != ".zip":
        raise ValueError(f"Expected .zip file, got: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        chat_txt_path = _pick_chat_txt_path(zf)
        chat_text = zf.read(chat_txt_path).decode("utf-8", errors="replace")

    return ZipChatSource(zip_path=str(zip_path), chat_txt_path=chat_txt_path, messages=parse_ios_chat_text(chat_text))


def parse_ios_export_dir(source_dir: Path) -> ZipChatSource:
    chat_path = discover_ios_chat_txt(source_dir)
    chat_text = chat_path.read_text(encoding="utf-8", errors="replace")
    return ZipChatSource(zip_path=str(source_dir), chat_txt_path=str(chat_path), messages=parse_ios_chat_text(chat_text))


def _escape(s: str) -> str:
    return html.escape(s, quote=False)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dt_local(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000.0)


def _month_key(m: Message) -> tuple[int, int]:
    dt = _dt_local(m.ts_ms)
    return (dt.year, dt.month)


def write_site(*, output_dir: Path, messages: list[Message], title: str) -> Path:
    site_dir = output_dir / "site"
    css = """
:root{color-scheme:light dark;--bg:Canvas;--fg:CanvasText;--muted:color-mix(in oklab, CanvasText 55%, Canvas 45%);--stroke:color-mix(in oklab, CanvasText 22%, Canvas 78%);--panel:color-mix(in oklab, Canvas 88%, CanvasText 12%);--me:color-mix(in oklab, #2b7 18%, Canvas 82%);--other:color-mix(in oklab, #48f 14%, Canvas 86%);}
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
main{padding:14px 18px 40px;max-width:980px}
.topbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}
.topbar .title{display:flex;flex-direction:column;gap:2px}
.topbar .title strong{font-size:14px}
.topbar .title span{color:var(--muted);font-size:12px}
.pill{border:1px solid var(--stroke);background:color-mix(in oklab, Canvas 92%, CanvasText 8%);border-radius:999px;padding:6px 10px;font-size:12px;text-decoration:none;white-space:nowrap}
.messages{display:flex;flex-direction:column;gap:8px}
.day{margin:18px 0 8px;padding-top:6px;border-top:1px dashed var(--stroke);color:var(--muted);font-size:12px}
.msg{display:grid;grid-template-columns:88px 1fr;gap:10px;align-items:start}
.ts{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px;padding-top:4px}
.bubble{border:1px solid var(--stroke);border-radius:14px;padding:10px 12px;background:var(--other)}
.meta{display:flex;gap:8px;align-items:baseline;margin-bottom:6px}
.sender{font-weight:600;font-size:12px}
.flags{color:var(--muted);font-size:12px}
.text{white-space:pre-wrap;word-wrap:break-word;font-size:13px;line-height:1.35}
.pager{display:flex;gap:10px;margin:16px 0 6px}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{position:relative;height:auto;border-right:none;border-bottom:1px solid var(--stroke)}}
"""
    _write_text(site_dir / "assets" / "style.css", css.strip() + "\n")

    if not messages:
        index = f"""<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{_escape(title)}</title><link rel="stylesheet" href="assets/style.css"/></head><body><main style="padding:16px">No messages.</main></body></html>"""
        _write_text(site_dir / "index.html", index)
        return site_dir / "index.html"

    messages = sorted(messages, key=lambda mm: (mm.ts_ms, mm.id))
    # Build month buckets
    buckets: dict[tuple[int, int], list[Message]] = {}
    for m in messages:
        buckets.setdefault(_month_key(m), []).append(m)
    month_keys = sorted(buckets.keys())

    # Nav HTML
    years: dict[int, list[tuple[int, int]]] = {}
    for y, mo in month_keys:
        years.setdefault(y, []).append((y, mo))
    nav_parts: list[str] = []
    for y, months in years.items():
        nav_parts.append(f'<div class="year">{y}</div><ul>')
        for yy, mm in months:
            ym = f"{yy:04d}-{mm:02d}"
            nav_parts.append(f'<li><a href="{ym}.html">{ym}</a></li>')
        nav_parts.append("</ul>")
    nav_html = "\n".join(nav_parts)

    # Index page
    subtitle = f"{len(messages):,} messages"
    index_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_escape(title)}</title><link rel="stylesheet" href="assets/style.css"/></head>
<body><div class="layout"><nav><header><strong>{_escape(title)}</strong><span>{_escape(subtitle)}</span></header><div class="section">{nav_html}</div></nav>
<main><div class="topbar"><div class="title"><strong>Chat timeline</strong><span>Select a month on the left.</span></div></div></main>
</div></body></html>"""
    _write_text(site_dir / "index.html", index_html)

    # Month pages
    for idx, (y, mo) in enumerate(month_keys):
        prev_k = month_keys[idx - 1] if idx > 0 else None
        next_k = month_keys[idx + 1] if idx < len(month_keys) - 1 else None
        ym = f"{y:04d}-{mo:02d}"
        bucket = buckets[(y, mo)]

        pager = []
        pager.append(f'<a class="pill" href="{prev_k[0]:04d}-{prev_k[1]:02d}.html">← {prev_k[0]:04d}-{prev_k[1]:02d}</a>' if prev_k else '<span class="pill" style="opacity:.55">← None</span>')
        pager.append('<a class="pill" href="index.html">Index</a>')
        pager.append(f'<a class="pill" href="{next_k[0]:04d}-{next_k[1]:02d}.html">{next_k[0]:04d}-{next_k[1]:02d} →</a>' if next_k else '<span class="pill" style="opacity:.55">None →</span>')
        pager_html = "\n".join(pager)

        msg_parts: list[str] = []
        current_day: str | None = None
        for m in bucket:
            dt = _dt_local(m.ts_ms)
            day = dt.strftime("%Y-%m-%d (%a)")
            if day != current_day:
                msg_parts.append(f'<div class="day">{_escape(day)}</div>')
                current_day = day
            ts = dt.strftime("%H:%M")
            sender = m.sender or ("System" if m.system else "Unknown")
            flags = []
            if m.has_media:
                flags.append("media")
            if m.system:
                flags.append("system")
            flags_s = f" • {', '.join(flags)}" if flags else ""
            msg_parts.append(
                f'<div class="msg"><div class="ts">{_escape(ts)}</div><div class="bubble"><div class="meta"><div class="sender">{_escape(sender)}</div><div class="flags">{_escape(flags_s)}</div></div><div class="text">{_escape(m.text)}</div></div></div>'
            )
        msgs_html = "\n".join(msg_parts)

        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_escape(title)} • {ym}</title><link rel="stylesheet" href="assets/style.css"/></head>
<body><div class="layout"><nav><header><strong>{_escape(title)}</strong><span>{_escape(subtitle)}</span></header><div class="section">{nav_html}</div></nav>
<main><div class="topbar"><div class="title"><strong>{ym}</strong><span>{len(bucket):,} messages</span></div><div class="pager">{pager_html}</div></div><div class="messages">{msgs_html}</div></main>
</div></body></html>"""
        _write_text(site_dir / f"{ym}.html", page)

    return site_dir / "index.html"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whatsapp_viz.py",
        description="Generate a standalone WhatsApp chat reader website from an iOS export ZIP or extracted folder.",
    )
    p.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=None,
        help="Source directory containing the export ZIP (default: Source/).",
    )
    p.add_argument("--source-dir", type=Path, default=Path("Source"))
    p.add_argument("--zip", type=Path, default=None)
    p.add_argument("--include-system", action="store_true")
    p.add_argument("--title", type=str, default="WhatsApp chat")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    output_dir: Path = Path("output")
    if output_dir.exists():
        if output_dir.is_dir():
            shutil.rmtree(output_dir)
        else:
            output_dir.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_dir: Path = args.source if args.source is not None else args.source_dir
    if args.zip is not None:
        zsrc = parse_ios_export_zip(args.zip)
    else:
        # Prefer an extracted export folder (e.g. contains `_chat.txt`) if present.
        if source_dir.exists() and (source_dir / "_chat.txt").exists():
            zsrc = parse_ios_export_dir(source_dir)
        elif source_dir.exists() and any(source_dir.glob("*.txt")):
            zsrc = parse_ios_export_dir(source_dir)
        else:
            zip_path = discover_ios_export_zip(source_dir)
            zsrc = parse_ios_export_zip(zip_path)
    messages = [m for m in zsrc.messages if (args.include_system or not m.system)]
    entry = write_site(output_dir=output_dir, messages=messages, title=args.title)
    print(f"Wrote {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

