from __future__ import annotations

import json
import re
from pathlib import Path

from video_notes.models import (
    CleanBlock,
    CleanDocument,
    CleanStats,
    CleanerConfig,
    SubtitleDocument,
    SubtitleEntry,
    parse_srt_time,
)

FILLER_PHRASES = frozenset(
    {
        "ööö",
        "öö",
        "ö",
        "hmm",
        "hm",
        "na",
        "no",
        "jó",
        "jo",
        "igen",
        "oké",
        "oke",
        "ok",
        "rendben",
        "köszi",
        "köszönöm",
        "koszi",
        "koszonom",
        "sziasztok",
        "szia",
        "hellóka",
        "hello",
        "helló",
        "ugye",
        "ugye.",
        "no,",
        "jó.",
        "jo.",
        "igen,",
        "na,",
    }
)

CHAT_PATTERNS = [
    re.compile(r"visszajelzést a hangra", re.IGNORECASE),
    re.compile(r"van egy kis csúszás", re.IGNORECASE),
    re.compile(r"írja is nekem", re.IGNORECASE),
    re.compile(r"képhang", re.IGNORECASE),
    re.compile(r"látom a chat", re.IGNORECASE),
    re.compile(r"itt tudsz kérdezni", re.IGNORECASE),
    re.compile(r"kiteszünk ilyen", re.IGNORECASE),
    re.compile(r"hangfalam", re.IGNORECASE),
    re.compile(r"zené hallgattam", re.IGNORECASE),
    re.compile(r"visszahallgatni", re.IGNORECASE),
    re.compile(r"üdv az újaknak", re.IGNORECASE),
    re.compile(r"meccsnézést", re.IGNORECASE),
    re.compile(r"jó éjszakát", re.IGNORECASE),
]

SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_key(text: str) -> str:
    lowered = normalize_text(text).lower()
    return lowered.rstrip(".,!?…")


def is_filler_only(text: str) -> bool:
    key = normalize_key(text)
    if not key:
        return True
    if key in FILLER_PHRASES:
        return True
    return bool(re.fullmatch(r"[öhm,\.!\?… ]+", key))


def matches_chat_noise(text: str, max_words: int) -> bool:
    words = normalize_text(text).split()
    if len(words) > max_words:
        return False
    return any(pattern.search(text) for pattern in CHAT_PATTERNS)


def is_noise_entry(entry: SubtitleEntry, config: CleanerConfig) -> bool:
    if not config.remove_fillers:
        return False

    text = normalize_text(entry.text)
    if not text:
        return True
    if is_filler_only(text):
        return True
    if matches_chat_noise(text, config.max_noise_words):
        return True
    return False


def should_merge(previous: SubtitleEntry, current: SubtitleEntry, gap_ms: int) -> bool:
    prev_end = parse_srt_time(previous.end)
    curr_start = parse_srt_time(current.start)
    gap = int((curr_start - prev_end).total_seconds() * 1000)

    if gap > gap_ms:
        return False

    previous_text = normalize_text(previous.text)
    if SENTENCE_END.search(previous_text):
        return gap <= 500

    return True


def merge_text(previous: str, current: str) -> str:
    left = normalize_text(previous)
    right = normalize_text(current)
    if not left:
        return right
    if not right:
        return left

    if left.endswith("-") and not left.endswith("--"):
        return left[:-1] + right

    return f"{left} {right}"


def build_clean_block(entries: list[SubtitleEntry]) -> CleanBlock:
    text = entries[0].text
    for entry in entries[1:]:
        text = merge_text(text, entry.text)

    return CleanBlock(
        start=entries[0].start,
        end=entries[-1].end,
        text=normalize_text(text),
        source_indices=[entry.index for entry in entries],
    )


def remove_duplicates(entries: list[SubtitleEntry]) -> list[SubtitleEntry]:
    unique: list[SubtitleEntry] = []
    previous_key: str | None = None

    for entry in entries:
        key = normalize_key(entry.text)
        if key and key == previous_key:
            continue
        unique.append(entry)
        previous_key = key or previous_key

    return unique


def filter_noise(
    entries: list[SubtitleEntry],
    config: CleanerConfig,
) -> tuple[list[SubtitleEntry], int]:
    filtered: list[SubtitleEntry] = []
    removed = 0

    for entry in entries:
        if is_noise_entry(entry, config):
            removed += 1
            continue
        filtered.append(entry)

    return filtered, removed


def merge_entries(
    entries: list[SubtitleEntry],
    config: CleanerConfig,
) -> list[CleanBlock]:
    if not entries:
        return []

    if not config.merge_blocks:
        return [build_clean_block([entry]) for entry in entries]

    blocks: list[CleanBlock] = []
    buffer = [entries[0]]

    for entry in entries[1:]:
        if should_merge(buffer[-1], entry, config.merge_gap_ms):
            buffer.append(entry)
            continue

        blocks.append(build_clean_block(buffer))
        buffer = [entry]

    blocks.append(build_clean_block(buffer))
    return blocks


def filter_short_blocks(
    blocks: list[CleanBlock],
    config: CleanerConfig,
) -> list[CleanBlock]:
    kept: list[CleanBlock] = []
    for block in blocks:
        if block.word_count < config.min_words_per_block and is_filler_only(block.text):
            continue
        kept.append(block)
    return kept


def compute_clean_stats(
    original_count: int,
    removed_count: int,
    blocks: list[CleanBlock],
) -> CleanStats:
    if not blocks:
        return CleanStats(
            original_entries=original_count,
            removed_entries=removed_count,
            merged_blocks=0,
            word_count=0,
            char_count=0,
            total_duration_seconds=0.0,
            avg_words_per_block=0.0,
            reduction_percent=100.0 if original_count else 0.0,
            first_timestamp="00:00:00,000",
            last_timestamp="00:00:00,000",
        )

    first_start = parse_srt_time(blocks[0].start)
    last_end = parse_srt_time(blocks[-1].end)
    word_count = sum(block.word_count for block in blocks)
    char_count = sum(len(block.text) for block in blocks)
    block_count = len(blocks)

    return CleanStats(
        original_entries=original_count,
        removed_entries=removed_count,
        merged_blocks=block_count,
        word_count=word_count,
        char_count=char_count,
        total_duration_seconds=round((last_end - first_start).total_seconds(), 2),
        avg_words_per_block=round(word_count / block_count, 2),
        reduction_percent=round(
            (1 - block_count / original_count) * 100,
            1,
        ) if original_count else 0.0,
        first_timestamp=blocks[0].start,
        last_timestamp=blocks[-1].end,
    )


def clean_document(
    document: SubtitleDocument,
    config: CleanerConfig | None = None,
) -> CleanDocument:
    settings = config or CleanerConfig()
    original_count = len(document.entries)

    deduped = remove_duplicates(document.entries)
    filtered, removed = filter_noise(deduped, settings)
    merged = merge_entries(filtered, settings)
    blocks = filter_short_blocks(merged, settings)

    clean = CleanDocument(
        source_file=document.source_file,
        blocks=blocks,
    )
    clean.stats = compute_clean_stats(original_count, removed, blocks)
    return clean


def load_subtitle_document(path: Path) -> SubtitleDocument:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return SubtitleDocument.model_validate(data)

    from video_notes.parser import parse_srt_file

    return parse_srt_file(path)


def export_clean_json(document: CleanDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
