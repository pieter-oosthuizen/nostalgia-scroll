from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from whatsapp_viz.models import Message


@dataclass(frozen=True, slots=True)
class ZipChatSource:
    zip_path: str
    chat_txt_path: str
    messages: list[Message]


_IOS_LINE_RE = re.compile(
    # Example:
    #   [27/11/2020, 11:28:27] Name: Message
    #   11/27/20, 11:28 PM - Name: Message
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
    # Common extracted export filename is "_chat.txt"
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
    # Heuristic: prefer something containing 'chat' (common), else largest text file.
    chatish = [c for c in candidates if "chat" in Path(c).name.lower()]
    if chatish:
        return sorted(chatish, key=len)[0]
    return max(candidates, key=lambda fn: zf.getinfo(fn).file_size)


def _local_tz() -> ZoneInfo:
    # Best-effort local timezone; fall back to UTC.
    try:
        return ZoneInfo(str(datetime.now().astimezone().tzinfo))
    except Exception:
        return ZoneInfo("UTC")


def _parse_ts(date_s: str, time_s: str, sec_s: str | None, ampm: str | None, tz: ZoneInfo) -> datetime:
    # WhatsApp iOS exports vary; support both 12h w/ AM/PM and 24h without.
    # Date can be D/M/YY or M/D/YY depending on locale; we can't know reliably.
    # We'll assume M/D/YY first, then D/M/YY fallback.
    sec = sec_s or "00"
    year_token = date_s.split("/")[-1]
    yfmt = "%Y" if len(year_token) == 4 else "%y"
    if ampm:
        fmt = f"%m/%d/{yfmt} %I:%M:%S %p"
        s = f"{date_s} {time_s}:{sec} {ampm}"
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            fmt2 = f"%d/%m/{yfmt} %I:%M:%S %p"
            dt = datetime.strptime(s, fmt2)
    else:
        fmt = f"%m/%d/{yfmt} %H:%M:%S"
        s = f"{date_s} {time_s}:{sec}"
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            fmt2 = f"%d/%m/{yfmt} %H:%M:%S"
            dt = datetime.strptime(s, fmt2)
    return dt.replace(tzinfo=tz)


def parse_ios_chat_text(chat_text: str) -> list[Message]:
    tz = _local_tz()
    messages: list[Message] = []

    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        msg = Message(
            id=current["id"],
            ts_ms=current["ts_ms"],
            ts_iso=current["ts_iso"],
            sender=current["sender"],
            text=current["text"].rstrip("\n"),
            has_media=current["has_media"],
            system=current["system"],
        )
        messages.append(msg)
        current = None

    lines = chat_text.splitlines()
    msg_id = 0
    for raw in lines:
        m = _IOS_LINE_RE.match(raw)
        if not m:
            # Continuation line of previous message (multi-line text)
            if current is not None:
                current["text"] += "\n" + raw
            continue

        flush()
        date_s = m.group("br_date") or m.group("date")
        time_s = m.group("br_time") or m.group("time")
        sec_s = m.group("br_sec") or m.group("sec")
        ampm = m.group("ampm")
        body = m.group("body") or ""

        dt = _parse_ts(date_s, time_s, sec_s, ampm, tz=tz)
        ts_ms = int(dt.timestamp() * 1000)
        ts_iso = dt.isoformat()

        sender: str | None
        text: str
        system: bool
        has_media = False

        # Typical format: "Name: message"
        if ": " in body:
            sender, text = body.split(": ", 1)
            system = False
        else:
            sender = None
            text = body
            system = True

        lowered = text.strip().lower()
        if lowered in {"<media omitted>", "image omitted", "video omitted"} or "omitted" in lowered:
            has_media = True

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
    return messages


def parse_ios_export_zip(zip_path: Path) -> ZipChatSource:
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    if zip_path.suffix.lower() != ".zip":
        raise ValueError(f"Expected .zip file, got: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        chat_txt_path = _pick_chat_txt_path(zf)
        raw_bytes = zf.read(chat_txt_path)
        # iOS exports are typically UTF-8; try replacement to avoid hard failures.
        chat_text = raw_bytes.decode("utf-8", errors="replace")

    messages = parse_ios_chat_text(chat_text)
    # Ensure chronological order (can be out of order when parsing locale ambiguity)
    messages.sort(key=lambda mm: (mm.ts_ms, mm.id))
    # Reassign IDs in sorted order to keep stable monotonic IDs
    messages = [
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

    return ZipChatSource(zip_path=str(zip_path), chat_txt_path=chat_txt_path, messages=messages)


def parse_ios_export_dir(source_dir: Path) -> ZipChatSource:
    chat_path = discover_ios_chat_txt(source_dir)
    chat_text = chat_path.read_text(encoding="utf-8", errors="replace")
    messages = parse_ios_chat_text(chat_text)
    messages.sort(key=lambda mm: (mm.ts_ms, mm.id))
    messages = [
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
    return ZipChatSource(zip_path=str(source_dir), chat_txt_path=str(chat_path), messages=messages)

