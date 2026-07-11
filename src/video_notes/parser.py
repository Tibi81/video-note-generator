from __future__ import annotations

from pathlib import Path

import srt

from video_notes.models import (
    SubtitleDocument,
    SubtitleEntry,
    format_srt_time,
    resolve_source_name,
)


def read_subtitle_text(path: Path, encoding: str = "utf-8") -> str:
    """Feliratfájl beolvasása, BOM kezeléssel."""
    raw = path.read_bytes()
    for enc in (encoding, "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Nem sikerült dekódolni a fájlt: {path}")


def parse_srt_content(content: str) -> list[SubtitleEntry]:
    """SRT szöveg → strukturált bejegyzések."""
    subtitles = list(srt.parse(content))
    entries: list[SubtitleEntry] = []

    for item in subtitles:
        text = item.content.strip()
        if not text:
            continue

        entries.append(
            SubtitleEntry(
                index=item.index,
                start=format_srt_time(item.start),
                end=format_srt_time(item.end),
                text=text,
            )
        )

    return entries


def parse_srt_file(path: Path, encoding: str = "utf-8") -> SubtitleDocument:
    """SRT fájl beolvasása és strukturált dokumentummá alakítása."""
    if not path.exists():
        raise FileNotFoundError(f"A feliratfájl nem található: {path}")

    content = read_subtitle_text(path, encoding=encoding)
    entries = parse_srt_content(content)

    document = SubtitleDocument(
        source_file=resolve_source_name(path),
        entries=entries,
    )
    document.stats = document.compute_stats()
    return document


def export_json(document: SubtitleDocument, output_path: Path) -> Path:
    """Dokumentum mentése JSON formátumban."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
