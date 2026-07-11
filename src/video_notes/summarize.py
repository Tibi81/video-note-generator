from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from video_notes.ai import AIProvider, create_ai_provider, extract_json_object, load_prompt
from video_notes.models import (
    AIConfig,
    Chapter,
    ChapterDocument,
    ProcessedChapter,
    ScreenshotHint,
    SummaryDocument,
    SummaryStats,
    parse_srt_time,
)


def load_chapter_document(path: Path) -> ChapterDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ChapterDocument.model_validate(data)


def normalize_timestamp(value: str, fallback: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return fallback.split(",")[0]

    if "," in cleaned:
        cleaned = cleaned.split(",")[0]

    match = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", cleaned)
    if not match:
        return fallback.split(",")[0]

    hours, minutes, seconds = map(int, match.groups())
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clamp_screenshot_timestamp(
    timestamp: str,
    chapter: Chapter,
) -> str:
    normalized = normalize_timestamp(timestamp, chapter.start)
    ts = parse_srt_time(f"{normalized},000")
    start = parse_srt_time(chapter.start)
    end = parse_srt_time(chapter.end)

    if ts < start:
        return chapter.start.split(",")[0]
    if ts > end:
        return chapter.end.split(",")[0]
    return normalized


def parse_processed_chapter(
    chapter: Chapter,
    payload: dict,
) -> ProcessedChapter:
    screenshot_data = payload.get("screenshot")
    screenshot: ScreenshotHint | None = None

    if isinstance(screenshot_data, dict):
        timestamp = screenshot_data.get("timestamp")
        reason = screenshot_data.get("reason")
        if timestamp and reason:
            screenshot = ScreenshotHint(
                timestamp=clamp_screenshot_timestamp(str(timestamp), chapter),
                reason=str(reason).strip(),
            )

    key_points = payload.get("key_points") or []
    keywords = payload.get("keywords") or []

    if not isinstance(key_points, list):
        key_points = [str(key_points)]
    if not isinstance(keywords, list):
        keywords = [str(keywords)]

    practice_task = payload.get("practice_task")
    if practice_task is not None:
        practice_task = str(practice_task).strip() or None

    return ProcessedChapter(
        index=chapter.index,
        title=chapter.title,
        start=chapter.start,
        end=chapter.end,
        summary=str(payload.get("summary", "")).strip(),
        key_points=[str(point).strip() for point in key_points if str(point).strip()],
        keywords=[str(word).strip() for word in keywords if str(word).strip()],
        practice_task=practice_task,
        screenshot=screenshot,
    )


def summarize_chapter(
    chapter: Chapter,
    provider: AIProvider,
    prompt_template: str,
) -> ProcessedChapter:
    prompt = prompt_template.format(
        title=chapter.title,
        start=chapter.start,
        end=chapter.end,
        transcript=chapter.text,
    )
    raw = provider.complete(
        system_prompt=(
            "You are a precise assistant that returns only valid JSON "
            "for Hungarian webdesign study notes."
        ),
        user_prompt=prompt,
    )
    payload = extract_json_object(raw)
    return parse_processed_chapter(chapter, payload)


def summarize_document(
    document: ChapterDocument,
    ai_config: AIConfig,
    prompts_dir: Path | None = None,
    provider: AIProvider | None = None,
    on_progress: Callable[[int, int, Chapter], None] | None = None,
) -> SummaryDocument:
    ai = provider or create_ai_provider(ai_config)
    prompt_template = load_prompt("summarize", prompts_dir=prompts_dir)

    processed: list[ProcessedChapter] = []
    total = len(document.chapters)
    for chapter in document.chapters:
        if on_progress:
            on_progress(chapter.index, total, chapter)
        processed.append(summarize_chapter(chapter, ai, prompt_template))

    screenshot_count = sum(1 for chapter in processed if chapter.screenshot is not None)
    word_count = sum(len(chapter.summary.split()) for chapter in processed)

    result = SummaryDocument(
        source_file=document.source_file,
        chapters=processed,
    )
    result.stats = SummaryStats(
        chapter_count=len(document.chapters),
        processed_count=len(processed),
        screenshot_count=screenshot_count,
        provider=ai_config.provider,
        model=ai_config.model,
        word_count=word_count,
    )
    return result


def export_summary_json(document: SummaryDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
