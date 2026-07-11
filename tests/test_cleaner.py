from pathlib import Path

from video_notes.cleaner import (
    clean_document,
    is_filler_only,
    is_noise_entry,
    matches_chat_noise,
    merge_text,
    remove_duplicates,
)
from video_notes.models import CleanerConfig, SubtitleEntry
from video_notes.parser import parse_srt_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_is_filler_only():
    assert is_filler_only("No,")
    assert is_filler_only("ööö")
    assert not is_filler_only("Auto Layout beállítása")


def test_matches_chat_noise():
    assert matches_chat_noise("Kérnék visszajelzést a hangra.", max_words=4)
    assert not matches_chat_noise(
        "Az Auto Layout paddinget és gap-et kezel a komponensekben.",
        max_words=4,
    )


def test_merge_text_hyphen():
    assert merge_text("webdesi-", "gn") == "webdesign"


def test_remove_duplicates():
    entries = [
        SubtitleEntry(index=1, start="00:00:01,000", end="00:00:02,000", text="Na"),
        SubtitleEntry(index=2, start="00:00:02,000", end="00:00:03,000", text="na"),
        SubtitleEntry(index=3, start="00:00:03,000", end="00:00:04,000", text="Téma"),
    ]
    result = remove_duplicates(entries)
    assert len(result) == 2


def test_clean_document_merges_and_filters_noise():
    document = parse_srt_file(FIXTURES / "noisy.srt")
    cleaned = clean_document(document, CleanerConfig())

    assert cleaned.stats is not None
    assert cleaned.stats.removed_entries >= 3
    assert cleaned.stats.merged_blocks < cleaned.stats.original_entries
    assert any("Auto Layout" in block.text for block in cleaned.blocks)
    assert all("visszajelzést a hangra" not in block.text for block in cleaned.blocks)


def test_clean_document_from_parsed_json(tmp_path: Path):
    document = parse_srt_file(FIXTURES / "sample.srt")
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")

    from video_notes.cleaner import load_subtitle_document

    loaded = load_subtitle_document(parsed_path)
    cleaned = clean_document(loaded)

    assert cleaned.stats is not None
    assert cleaned.stats.merged_blocks <= loaded.stats.entry_count
