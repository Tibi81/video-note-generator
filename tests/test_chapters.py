from pathlib import Path

from video_notes.chapters import (
    detect_chapters_heuristic,
    expand_blocks_to_segments,
    guess_title,
    split_block_into_segments,
)
from video_notes.cleaner import clean_document
from video_notes.models import ChaptersConfig, CleanBlock
from video_notes.parser import parse_srt_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_split_long_block_into_segments():
    block = CleanBlock(
        start="00:10:00,000",
        end="00:20:00,000",
        text="Első mondat. Második mondat. " + " ".join(["töltő"] * 300),
        source_indices=[1, 2],
    )
    segments = split_block_into_segments(block, max_words=80)
    assert len(segments) > 1
    assert segments[0].start == "00:10:00,000"
    assert segments[-1].end == "00:20:00,000"


def test_guess_title_uses_keyword():
    title = guess_title("Ma az Auto Layout beállításait nézzük részletesen.", 1)
    assert title == "Auto Layout"


def test_detect_chapters_heuristic_count_range():
    document = parse_srt_file(FIXTURES / "noisy.srt")
    cleaned = clean_document(document)
    config = ChaptersConfig(min_chapters=2, max_chapters=8, max_words_per_segment=40)
    result = detect_chapters_heuristic(cleaned, config)

    assert result.stats is not None
    assert 2 <= result.stats.chapter_count <= 8
    assert all(chapter.title for chapter in result.chapters)
    assert all(chapter.start <= chapter.end for chapter in result.chapters)


def test_expand_blocks_to_segments_preserves_order():
    document = parse_srt_file(FIXTURES / "sample.srt")
    cleaned = clean_document(document)
    segments = expand_blocks_to_segments(cleaned.blocks, max_words=10)
    assert len(segments) >= len(cleaned.blocks)
    assert segments[0].start <= segments[-1].start
