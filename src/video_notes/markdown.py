from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from video_notes.models import (
    MarkdownConfig,
    ProcessedChapter,
    ScreenshotRecord,
    ScreenshotsManifest,
    SummaryDocument,
    parse_srt_time,
)


def format_display_timestamp(value: str) -> str:
    return value.split(",")[0]


def format_duration_from_chapters(chapters: list[ProcessedChapter]) -> str:
    if not chapters:
        return "00:00:00"
    start = parse_srt_time(chapters[0].start)
    end = parse_srt_time(chapters[-1].end)
    total_seconds = int((end - start).total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def slugify_title(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned or "jegyzet"


def derive_note_title(document: SummaryDocument, config: MarkdownConfig) -> str:
    if config.title:
        return config.title

    source = Path(document.source_file).stem
    source = re.sub(r"\.hu$", "", source)
    source = re.sub(r"\s*\[[^\]]+\]$", "", source)
    return source.strip() or "Workshop jegyzet"


def render_chapter(
    chapter: ProcessedChapter,
    screenshot: ScreenshotRecord | None,
    config: MarkdownConfig,
) -> str:
    lines = [
        f"# {chapter.title}",
        "",
        f"⏱ {format_display_timestamp(chapter.start)}",
        "",
        chapter.summary,
        "",
    ]

    if screenshot is not None:
        if config.obsidian_wikilinks:
            lines.append(f"![[images/{screenshot.filename}]]")
        else:
            lines.append(f"![](images/{screenshot.filename})")
        lines.extend(["", f"*Screenshot: {screenshot.timestamp} — {screenshot.reason}*", ""])

    if chapter.key_points:
        lines.append("## Fő tanulságok")
        lines.append("")
        for point in chapter.key_points:
            lines.append(f"- {point}")
        lines.append("")

    if config.include_practice and chapter.practice_task:
        lines.append("## Gyakorlati feladat")
        lines.append("")
        lines.append(chapter.practice_task)
        lines.append("")

    if config.include_keywords and chapter.keywords:
        lines.append("## Kulcsszavak")
        lines.append("")
        lines.append(", ".join(f"`{keyword}`" for keyword in chapter.keywords))
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_markdown(
    document: SummaryDocument,
    manifest: ScreenshotsManifest | None = None,
    config: MarkdownConfig | None = None,
) -> str:
    settings = config or MarkdownConfig()
    title = derive_note_title(document, settings)
    screenshots = manifest.screenshots if manifest else []
    screenshot_by_chapter = {record.chapter_index: record for record in screenshots}

    frontmatter = [
        "---",
        f'title: "{title}"',
        f'source: "{document.source_file}"',
        f"date: {datetime.now().date().isoformat()}",
        f'duration: "{format_duration_from_chapters(document.chapters)}"',
        f"chapters: {len(document.chapters)}",
        "---",
        "",
        f"# {title}",
        "",
        "> Automatikusan generált tanulási jegyzet a video-note-generatorral.",
        "",
    ]

    body: list[str] = []
    for chapter in document.chapters:
        body.append(
            render_chapter(
                chapter,
                screenshot_by_chapter.get(chapter.index),
                settings,
            )
        )

    return "\n".join(frontmatter + body)


def export_markdown(
    content: str,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
