from __future__ import annotations

import json
import subprocess
from pathlib import Path

from video_notes.models import (
    ProcessedChapter,
    ScreenshotRecord,
    ScreenshotsConfig,
    ScreenshotsManifest,
    SummaryDocument,
    parse_srt_time,
)


def load_summary_document(path: Path) -> SummaryDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SummaryDocument.model_validate(data)


def timestamp_to_ffmpeg(value: str) -> str:
    """SRT időbélyeg → ffmpeg -ss formátum (ponttal: HH:MM:SS.mmm)."""
    cleaned = value.strip()
    if "," in cleaned:
        time_part, ms_part = cleaned.split(",", 1)
        return f"{time_part}.{ms_part[:3].ljust(3, '0')}"
    if cleaned.count(":") == 2:
        return f"{cleaned}.000"
    return cleaned


def find_video_file(
    directory: Path,
    extensions: list[str] | None = None,
) -> Path:
    allowed = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in (extensions or [".mp4", ".webm", ".mkv", ".mov"])}
    matches = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    ]
    if not matches:
        raise FileNotFoundError(f"Nem található videófájl itt: {directory}")
    if len(matches) > 1:
        matches.sort(key=lambda item: item.stat().st_size, reverse=True)
    return matches[0]


def collect_screenshot_requests(
    document: SummaryDocument,
    config: ScreenshotsConfig,
) -> list[ScreenshotRecord]:
    records: list[ScreenshotRecord] = []
    image_index = 1
    timestamp_to_filename: dict[str, str] = {}

    for chapter in document.chapters:
        if chapter.screenshot is None:
            continue

        timestamp = chapter.screenshot.timestamp
        ffmpeg_ts = timestamp_to_ffmpeg(timestamp)

        if ffmpeg_ts in timestamp_to_filename:
            filename = timestamp_to_filename[ffmpeg_ts]
        else:
            filename = f"{image_index:03d}.{config.format}"
            timestamp_to_filename[ffmpeg_ts] = filename
            image_index += 1

        records.append(
            ScreenshotRecord(
                index=len(records) + 1,
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                timestamp=timestamp,
                filename=filename,
                reason=chapter.screenshot.reason,
            )
        )

    return records


def extract_frame(
    video_path: Path,
    timestamp: str,
    output_path: Path,
    config: ScreenshotsConfig,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_time = timestamp_to_ffmpeg(timestamp)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        ffmpeg_time,
        "-i",
        str(video_path),
        "-frames:v",
        "1",
    ]

    if config.width > 0:
        command.extend(["-vf", f"scale={config.width}:-1"])

    command.extend(["-y", str(output_path)])

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg hiba ({timestamp}): {result.stderr.strip() or result.stdout.strip()}"
        )
    if not output_path.exists():
        raise RuntimeError(f"A kép nem jött létre: {output_path}")


def extract_screenshots(
    document: SummaryDocument,
    video_path: Path,
    output_dir: Path,
    config: ScreenshotsConfig | None = None,
    images_subdir: str = "images",
) -> ScreenshotsManifest:
    settings = config or ScreenshotsConfig()
    images_dir = output_dir / images_subdir
    records = collect_screenshot_requests(document, settings)
    extracted_files: set[str] = set()

    for record in records:
        target = images_dir / record.filename
        if record.filename not in extracted_files:
            extract_frame(video_path, record.timestamp, target, settings)
            extracted_files.add(record.filename)
        record.extracted = True

    return ScreenshotsManifest(
        video_file=str(video_path.resolve()),
        images_dir=images_subdir,
        screenshots=records,
    )


def export_manifest(manifest: ScreenshotsManifest, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path


def load_manifest(path: Path) -> ScreenshotsManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ScreenshotsManifest.model_validate(data)


def screenshot_map_by_chapter(manifest: ScreenshotsManifest) -> dict[int, ScreenshotRecord]:
    return {record.chapter_index: record for record in manifest.screenshots}
