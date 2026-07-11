from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel, Field, computed_field


def format_srt_time(delta: timedelta) -> str:
    """Timedelta → SRT időformátum (HH:MM:SS,mmm)."""
    total_ms = int(delta.total_seconds() * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt_time(value: str) -> timedelta:
    """SRT időformátum (HH:MM:SS,mmm) → timedelta."""
    time_part, ms_part = value.split(",")
    hours, minutes, seconds = map(int, time_part.split(":"))
    milliseconds = int(ms_part)
    return timedelta(
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        milliseconds=milliseconds,
    )


class SubtitleEntry(BaseModel):
    """Egy SRT feliratblokk."""

    index: int
    start: str
    end: str
    text: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_ms(self) -> int:
        start_td = parse_srt_time(self.start)
        end_td = parse_srt_time(self.end)
        return max(0, int((end_td - start_td).total_seconds() * 1000))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        return len(self.text.split())


class SubtitleStats(BaseModel):
    """Összesítő statisztikák a feliratfájlhoz."""

    entry_count: int
    total_duration_seconds: float
    word_count: int
    char_count: int
    avg_block_duration_seconds: float
    avg_words_per_block: float
    first_timestamp: str
    last_timestamp: str


class SubtitleDocument(BaseModel):
    """Teljes feldolgozott felirat dokumentum."""

    source_file: str
    entries: list[SubtitleEntry] = Field(default_factory=list)
    stats: SubtitleStats | None = None

    def compute_stats(self) -> SubtitleStats:
        if not self.entries:
            return SubtitleStats(
                entry_count=0,
                total_duration_seconds=0.0,
                word_count=0,
                char_count=0,
                avg_block_duration_seconds=0.0,
                avg_words_per_block=0.0,
                first_timestamp="00:00:00,000",
                last_timestamp="00:00:00,000",
            )

        first_start = parse_srt_time(self.entries[0].start)
        last_end = parse_srt_time(self.entries[-1].end)
        total_duration = (last_end - first_start).total_seconds()

        word_count = sum(entry.word_count for entry in self.entries)
        char_count = sum(len(entry.text) for entry in self.entries)
        total_block_duration = sum(entry.duration_ms for entry in self.entries)

        entry_count = len(self.entries)

        return SubtitleStats(
            entry_count=entry_count,
            total_duration_seconds=round(total_duration, 2),
            word_count=word_count,
            char_count=char_count,
            avg_block_duration_seconds=round(
                total_block_duration / entry_count / 1000,
                2,
            ),
            avg_words_per_block=round(word_count / entry_count, 2),
            first_timestamp=self.entries[0].start,
            last_timestamp=self.entries[-1].end,
        )


class CleanBlock(BaseModel):
    """Összevont, tisztított szövegblokk időbélyegekkel."""

    start: str
    end: str
    text: str
    source_indices: list[int] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_ms(self) -> int:
        start_td = parse_srt_time(self.start)
        end_td = parse_srt_time(self.end)
        return max(0, int((end_td - start_td).total_seconds() * 1000))


class CleanStats(BaseModel):
    """Tisztítás statisztikái."""

    original_entries: int
    removed_entries: int
    merged_blocks: int
    word_count: int
    char_count: int
    total_duration_seconds: float
    avg_words_per_block: float
    reduction_percent: float
    first_timestamp: str
    last_timestamp: str


class CleanDocument(BaseModel):
    """Tisztított felirat dokumentum."""

    source_file: str
    blocks: list[CleanBlock] = Field(default_factory=list)
    stats: CleanStats | None = None


class CleanerConfig(BaseModel):
    """Cleaner beállítások."""

    remove_fillers: bool = True
    merge_blocks: bool = True
    merge_gap_ms: int = 2000
    min_words_per_block: int = 2
    max_noise_words: int = 4


def resolve_source_name(path: Path) -> str:
    """Relatív vagy abszolút fájlnév a dokumentum metaadatához."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path.resolve())
