from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from nostalgia_scroll.parse_ios import ZipChatSource, discover_ios_export_zip, parse_ios_export_dir, parse_ios_export_zip
from nostalgia_scroll.site import build_site


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nostalgia-scroll",
        description="Generate an offline, scrollable website from a WhatsApp chat export.",
    )
    p.add_argument(
        "--source-dir",
        type=Path,
        default=Path("Source"),
        help="Directory containing the WhatsApp export ZIP (default: Source/).",
    )
    p.add_argument(
        "--zip",
        type=Path,
        default=None,
        help="Path to a specific export ZIP (overrides --source-dir auto-discovery).",
    )
    p.add_argument(
        "--include-system",
        action="store_true",
        help="Include WhatsApp system messages in counts.",
    )
    p.add_argument(
        "--title",
        type=str,
        default="WhatsApp chat",
        help="Title shown in the generated site.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    source_dir: Path = args.source_dir
    output_dir: Path = Path("output")
    if output_dir.exists():
        if output_dir.is_dir():
            shutil.rmtree(output_dir)
        else:
            output_dir.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.zip is not None:
        zsrc: ZipChatSource = parse_ios_export_zip(args.zip)
    else:
        if source_dir.exists() and (source_dir / "_chat.txt").exists():
            zsrc = parse_ios_export_dir(source_dir)
        elif source_dir.exists() and any(source_dir.glob("*.txt")):
            zsrc = parse_ios_export_dir(source_dir)
        else:
            zip_path = discover_ios_export_zip(source_dir)
            zsrc = parse_ios_export_zip(zip_path)

    messages = [m for m in zsrc.messages if (args.include_system or not m.system)]
    entry = build_site(
        output_dir=output_dir,
        messages=messages,
        title=args.title,
        subtitle=f"{Path(zsrc.chat_txt_path).name} • {len(messages):,} messages",
        media_source_dir=source_dir if source_dir.exists() and source_dir.is_dir() else None,
    )
    print(f"Wrote {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

