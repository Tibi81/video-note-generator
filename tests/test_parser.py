from pathlib import Path

import pytest

from video_notes.models import parse_srt_time
from video_notes.parser import parse_srt_content, parse_srt_file


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_srt_time():
    assert parse_srt_time("00:01:20,500").total_seconds() == pytest.approx(80.5)


def test_parse_srt_content():
    content = (FIXTURES / "sample.srt").read_text(encoding="utf-8")
    entries = parse_srt_content(content)

    assert len(entries) == 3
    assert entries[0].index == 1
    assert entries[0].text == "Hellóka! Üdv mindenkinek."
    assert entries[0].start == "00:00:01,000"
    assert entries[0].end == "00:00:04,000"
    assert entries[2].word_count == 6


def test_parse_srt_file_stats():
    document = parse_srt_file(FIXTURES / "sample.srt")
    stats = document.stats

    assert stats is not None
    assert stats.entry_count == 3
    assert stats.word_count == 14
    assert stats.first_timestamp == "00:00:01,000"
    assert stats.last_timestamp == "00:00:10,000"
    assert stats.total_duration_seconds == pytest.approx(9.0)


def test_parse_srt_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_srt_file(FIXTURES / "missing.srt")
