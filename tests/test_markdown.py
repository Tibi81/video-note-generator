from video_notes.markdown import build_markdown
from video_notes.models import (
    MarkdownConfig,
    ProcessedChapter,
    ScreenshotHint,
    ScreenshotRecord,
    ScreenshotsConfig,
    ScreenshotsManifest,
    SummaryDocument,
)
from video_notes.screenshots import collect_screenshot_requests, timestamp_to_ffmpeg


def test_timestamp_to_ffmpeg_adds_milliseconds():
    assert timestamp_to_ffmpeg("00:12:30") == "00:12:30.000"
    assert timestamp_to_ffmpeg("00:12:30,500") == "00:12:30.500"


def test_collect_screenshot_requests_reuses_duplicate_timestamps():
    document = SummaryDocument(
        source_file="test.srt",
        chapters=[
            ProcessedChapter(
                index=1,
                title="A",
                start="00:00:00,000",
                end="00:01:00,000",
                summary="a",
                screenshot=ScreenshotHint(timestamp="00:00:10", reason="r1"),
            ),
            ProcessedChapter(
                index=2,
                title="B",
                start="00:01:00,000",
                end="00:02:00,000",
                summary="b",
                screenshot=ScreenshotHint(timestamp="00:00:10", reason="r2"),
            ),
        ],
    )

    records = collect_screenshot_requests(document, config=ScreenshotsConfig())
    filenames = {record.filename for record in records}
    assert len(records) == 2
    assert len(filenames) == 1


def test_build_markdown_contains_obsidian_links():
    summary = SummaryDocument(
        source_file="input/webinar.srt",
        chapters=[
            ProcessedChapter(
                index=1,
                title="Auto Layout",
                start="00:10:00,000",
                end="00:15:00,000",
                summary="Az Auto Layout bemutatása.",
                key_points=["⭐ Padding", "⭐ Gap"],
                keywords=["auto layout"],
                practice_task="Készíts egy Card komponenst.",
            )
        ],
    )
    manifest = ScreenshotsManifest(
        video_file="input/webinar.webm",
        images_dir="images",
        screenshots=[
            ScreenshotRecord(
                index=1,
                chapter_index=1,
                chapter_title="Auto Layout",
                timestamp="00:12:00",
                filename="001.png",
                reason="Figma panel",
                extracted=True,
            )
        ],
    )

    content = build_markdown(summary, manifest=manifest, config=MarkdownConfig())

    assert "# Auto Layout" in content
    assert "![[images/001.png]]" in content
    assert "## Gyakorlati feladat" in content
    assert "⭐ Padding" in content
