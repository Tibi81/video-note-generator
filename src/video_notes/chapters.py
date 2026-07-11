from __future__ import annotations

import json
import re
from pathlib import Path

from video_notes.ai import (
    create_ai_provider,
    extract_json_array,
    load_prompt,
    render_prompt,
)
from video_notes.models import (
    AIConfig,
    Chapter,
    ChapterDocument,
    ChapterStats,
    ChaptersConfig,
    CleanBlock,
    CleanDocument,
    TextSegment,
    TopicKeyword,
    format_srt_time,
    parse_srt_time,
)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def load_clean_document(path: Path) -> CleanDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CleanDocument.model_validate(data)


def gap_between_blocks(previous: CleanBlock, current: CleanBlock) -> float:
    prev_end = parse_srt_time(previous.end)
    curr_start = parse_srt_time(current.start)
    return max(0.0, (curr_start - prev_end).total_seconds())


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_block_into_segments(
    block: CleanBlock,
    max_words: int,
) -> list[TextSegment]:
    if block.word_count <= max_words:
        return [
            TextSegment(
                start=block.start,
                end=block.end,
                text=block.text,
                source_indices=block.source_indices,
            )
        ]

    sentences = split_sentences(block.text)
    if not sentences:
        return [
            TextSegment(
                start=block.start,
                end=block.end,
                text=block.text,
                source_indices=block.source_indices,
            )
        ]

    block_start = parse_srt_time(block.start)
    block_end = parse_srt_time(block.end)
    total_ms = max(1, int((block_end - block_start).total_seconds() * 1000))
    total_words = block.word_count

    segments: list[TextSegment] = []
    buffer: list[str] = []
    buffer_words = 0
    segment_start_word = 0

    def flush(end_word: int) -> None:
        nonlocal buffer, buffer_words, segment_start_word
        if not buffer:
            return

        start_ratio = segment_start_word / total_words
        end_ratio = end_word / total_words
        start_ms = int(total_ms * start_ratio)
        end_ms = max(start_ms + 1, int(total_ms * end_ratio))

        from datetime import timedelta

        seg_start = block_start + timedelta(milliseconds=start_ms)
        seg_end = block_start + timedelta(milliseconds=min(end_ms, total_ms))
        if seg_end > block_end:
            seg_end = block_end

        segments.append(
            TextSegment(
                start=format_srt_time(seg_start),
                end=format_srt_time(seg_end),
                text=" ".join(buffer),
                source_indices=block.source_indices,
            )
        )
        buffer = []
        buffer_words = 0
        segment_start_word = end_word

    running_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if buffer and buffer_words + sentence_words > max_words:
            flush(running_words)
        buffer.append(sentence)
        buffer_words += sentence_words
        running_words += sentence_words

    flush(running_words)
    return segments


def expand_blocks_to_segments(
    blocks: list[CleanBlock],
    max_words: int,
) -> list[TextSegment]:
    segments: list[TextSegment] = []
    for block in blocks:
        segments.extend(split_block_into_segments(block, max_words=max_words))
    return segments


def guess_title(
    text: str,
    fallback_index: int,
    topic_keywords: list[TopicKeyword],
) -> str:
    lowered = text.lower()
    generic_match: str | None = None
    generic_keywords = {entry.keyword.lower() for entry in topic_keywords if entry.generic}

    for entry in topic_keywords:
        keyword = entry.keyword.lower()
        if keyword in lowered:
            if keyword in generic_keywords:
                generic_match = generic_match or entry.title
                continue
            return entry.title

    first_sentence = split_sentences(text)[0] if text else ""
    if generic_match and len(first_sentence) < 20:
        return generic_match

    if not first_sentence:
        return generic_match or f"Fejezet {fallback_index}"

    title = first_sentence.strip()
    if len(title) > 72:
        title = title[:69].rsplit(" ", 1)[0] + "..."

    return title[0].upper() + title[1:] if title else (generic_match or f"Fejezet {fallback_index}")


def gap_between_segments(previous: TextSegment, current: TextSegment) -> float:
    prev_end = parse_srt_time(previous.end)
    curr_start = parse_srt_time(current.start)
    return max(0.0, (curr_start - prev_end).total_seconds())


def target_words_per_chapter(
    total_words: int,
    config: ChaptersConfig,
) -> int:
    target_count = (config.min_chapters + config.max_chapters) // 2
    return max(120, int(total_words / target_count))


def build_chapter_from_segments(
    segments: list[TextSegment],
    index: int,
    topic_keywords: list[TopicKeyword],
) -> Chapter:
    text = " ".join(segment.text for segment in segments)
    source_indices: list[int] = []
    for segment in segments:
        source_indices.extend(segment.source_indices)

    return Chapter(
        index=index,
        title=guess_title(text, index, topic_keywords),
        start=segments[0].start,
        end=segments[-1].end,
        text=text,
        source_indices=sorted(set(source_indices)),
    )


def detect_chapters_heuristic(
    document: CleanDocument,
    config: ChaptersConfig,
) -> ChapterDocument:
    segments = expand_blocks_to_segments(
        document.blocks,
        max_words=config.max_words_per_segment,
    )
    if not segments:
        return ChapterDocument(source_file=document.source_file, chapters=[])

    target_words = target_words_per_chapter(
        sum(segment.word_count for segment in segments),
        config,
    )

    grouped: list[list[TextSegment]] = []
    buffer: list[TextSegment] = []
    buffer_words = 0

    for idx, segment in enumerate(segments):
        if buffer:
            gap = gap_between_segments(buffer[-1], segment)
            should_split = (
                buffer_words + segment.word_count > int(target_words * 1.35)
                or (
                    buffer_words >= int(target_words * 0.75)
                    and gap >= config.gap_threshold_seconds
                )
            )
            if should_split:
                grouped.append(buffer)
                buffer = []
                buffer_words = 0

        buffer.append(segment)
        buffer_words += segment.word_count

        if idx == len(segments) - 1 and buffer:
            grouped.append(buffer)

    chapters = [
        build_chapter_from_segments(group, index, config.topic_keywords)
        for index, group in enumerate(grouped, start=1)
    ]

    chapters = rebalance_chapters(chapters, config)
    for idx, chapter in enumerate(chapters, start=1):
        chapter.index = idx

    result = ChapterDocument(source_file=document.source_file, chapters=chapters)
    result.stats = compute_chapter_stats(result, method="heuristic", segment_count=len(segments))
    return result


def rebalance_chapters(
    chapters: list[Chapter],
    config: ChaptersConfig,
) -> list[Chapter]:
    if not chapters:
        return chapters

    balanced = chapters

    while len(balanced) > config.max_chapters and len(balanced) > 1:
        merge_index = min(
            range(len(balanced) - 1),
            key=lambda i: balanced[i].word_count + balanced[i + 1].word_count,
        )
        left = balanced[merge_index]
        right = balanced[merge_index + 1]
        merged = Chapter(
            index=left.index,
            title=left.title,
            start=left.start,
            end=right.end,
            text=f"{left.text} {right.text}".strip(),
            source_indices=sorted(set(left.source_indices + right.source_indices)),
        )
        balanced = balanced[:merge_index] + [merged] + balanced[merge_index + 2 :]

    while len(balanced) < config.min_chapters:
        split_index = max(range(len(balanced)), key=lambda i: balanced[i].word_count)
        chapter = balanced[split_index]
        sentences = split_sentences(chapter.text)
        if len(sentences) < 2:
            break

        midpoint = len(sentences) // 2
        left_text = " ".join(sentences[:midpoint])
        right_text = " ".join(sentences[midpoint:])

        chapter_start = parse_srt_time(chapter.start)
        chapter_end = parse_srt_time(chapter.end)
        total_ms = max(1, int((chapter_end - chapter_start).total_seconds() * 1000))
        from datetime import timedelta

        split_td = chapter_start + timedelta(milliseconds=total_ms // 2)
        split_at = format_srt_time(split_td)

        left = Chapter(
            index=chapter.index,
            title=guess_title(left_text, chapter.index, config.topic_keywords),
            start=chapter.start,
            end=split_at,
            text=left_text,
            source_indices=chapter.source_indices,
        )
        right = Chapter(
            index=chapter.index + 1,
            title=guess_title(right_text, chapter.index + 1, config.topic_keywords),
            start=split_at,
            end=chapter.end,
            text=right_text,
            source_indices=chapter.source_indices,
        )
        balanced = balanced[:split_index] + [left, right] + balanced[split_index + 1 :]

    return balanced


def format_transcript_chunk(segments: list[TextSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        timestamp = segment.start.split(",")[0]
        lines.append(f"[{timestamp}] {segment.text}")
    return "\n".join(lines)


def chunk_segments_by_duration(
    segments: list[TextSegment],
    chunk_minutes: int,
) -> list[list[TextSegment]]:
    if not segments:
        return []

    chunks: list[list[TextSegment]] = []
    current: list[TextSegment] = []
    chunk_start = parse_srt_time(segments[0].start)
    chunk_limit = chunk_minutes * 60

    for segment in segments:
        seg_start = parse_srt_time(segment.start)
        if current and (seg_start - chunk_start).total_seconds() >= chunk_limit:
            chunks.append(current)
            current = [segment]
            chunk_start = seg_start
        else:
            if not current:
                chunk_start = seg_start
            current.append(segment)

    if current:
        chunks.append(current)

    return chunks


def normalize_ai_timestamp(value: str) -> str:
    value = value.strip()
    if "," in value:
        return value
    if value.count(":") == 2:
        return f"{value},000"
    return value


def detect_chapters_ai(
    document: CleanDocument,
    chapters_config: ChaptersConfig,
    ai_config: AIConfig,
    prompts_dir: Path | None = None,
    prompt_context: dict[str, str] | None = None,
) -> ChapterDocument:
    segments = expand_blocks_to_segments(
        document.blocks,
        max_words=chapters_config.max_words_per_segment,
    )
    if not segments:
        return ChapterDocument(source_file=document.source_file, chapters=[])

    provider = create_ai_provider(ai_config)
    prompt_template = load_prompt("chapter", prompts_dir=prompts_dir)
    context = prompt_context or {}
    chunks = chunk_segments_by_duration(
        segments,
        chunk_minutes=chapters_config.chunk_duration_minutes,
    )

    detected: list[tuple[str, str]] = []
    for chunk in chunks:
        prompt = render_prompt(
            prompt_template,
            transcript=format_transcript_chunk(chunk),
            **context,
        )
        raw = provider.complete(
            system_prompt="You are a precise assistant that returns only valid JSON.",
            user_prompt=prompt,
        )
        for item in extract_json_array(raw):
            title = str(item.get("title", "")).strip()
            start = normalize_ai_timestamp(str(item.get("start", "")).strip())
            if title and start:
                detected.append((start, title))

    if not detected:
        raise RuntimeError("Az AI nem adott vissza fejezeteket.")

    detected.sort(key=lambda item: parse_srt_time(item[0]))
    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for start, title in detected:
        if start in seen:
            continue
        seen.add(start)
        deduped.append((start, title))

    chapters: list[Chapter] = []
    for idx, (start, title) in enumerate(deduped):
        end = deduped[idx + 1][0] if idx + 1 < len(deduped) else segments[-1].end
        chapter_segments = [
            segment
            for segment in segments
            if parse_srt_time(segment.start) >= parse_srt_time(start)
            and parse_srt_time(segment.start) < parse_srt_time(end)
        ]
        if not chapter_segments and idx == len(deduped) - 1:
            chapter_segments = [
                segment
                for segment in segments
                if parse_srt_time(segment.start) >= parse_srt_time(start)
            ]

        text = " ".join(segment.text for segment in chapter_segments)
        source_indices: list[int] = []
        for segment in chapter_segments:
            source_indices.extend(segment.source_indices)

        chapters.append(
            Chapter(
                index=idx + 1,
                title=title,
                start=start,
                end=end if idx + 1 < len(deduped) else segments[-1].end,
                text=text,
                source_indices=sorted(set(source_indices)),
            )
        )

    result = ChapterDocument(source_file=document.source_file, chapters=chapters)
    result.stats = compute_chapter_stats(result, method="ai", segment_count=len(segments))
    return result


def detect_chapters(
    document: CleanDocument,
    config: ChaptersConfig,
    ai_config: AIConfig | None = None,
    prompts_dir: Path | None = None,
    prompt_context: dict[str, str] | None = None,
) -> ChapterDocument:
    if config.method == "ai":
        if ai_config is None:
            raise RuntimeError("AI módhoz ai_config szükséges.")
        return detect_chapters_ai(
            document,
            chapters_config=config,
            ai_config=ai_config,
            prompts_dir=prompts_dir,
            prompt_context=prompt_context,
        )
    return detect_chapters_heuristic(document, config)


def compute_chapter_stats(
    document: ChapterDocument,
    method: str,
    segment_count: int,
) -> ChapterStats:
    if not document.chapters:
        return ChapterStats(
            chapter_count=0,
            segment_count=segment_count,
            word_count=0,
            total_duration_seconds=0.0,
            avg_words_per_chapter=0.0,
            avg_chapter_duration_seconds=0.0,
            method=method,
            first_timestamp="00:00:00,000",
            last_timestamp="00:00:00,000",
        )

    first_start = parse_srt_time(document.chapters[0].start)
    last_end = parse_srt_time(document.chapters[-1].end)
    word_count = sum(chapter.word_count for chapter in document.chapters)
    chapter_count = len(document.chapters)
    total_duration = (last_end - first_start).total_seconds()
    total_chapter_duration = sum(chapter.duration_ms for chapter in document.chapters)

    return ChapterStats(
        chapter_count=chapter_count,
        segment_count=segment_count,
        word_count=word_count,
        total_duration_seconds=round(total_duration, 2),
        avg_words_per_chapter=round(word_count / chapter_count, 2),
        avg_chapter_duration_seconds=round(
            total_chapter_duration / chapter_count / 1000,
            2,
        ),
        method=method,
        first_timestamp=document.chapters[0].start,
        last_timestamp=document.chapters[-1].end,
    )


def export_chapters_json(document: ChapterDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
