from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Message:
    id: int
    ts_ms: int
    ts_iso: str
    sender: str | None
    text: str
    has_media: bool
    system: bool

