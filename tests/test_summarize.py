from video_notes.models import Chapter
from video_notes.summarize import clamp_screenshot_timestamp, parse_processed_chapter


def test_parse_processed_chapter_with_screenshot():
    chapter = Chapter(
        index=1,
        title="Auto Layout",
        start="00:10:00,000",
        end="00:15:00,000",
        text="Az Auto Layout beállítása.",
    )
    payload = {
        "summary": "Az oktató bemutatja az Auto Layoutot.",
        "key_points": ["Padding", "Gap"],
        "keywords": ["auto layout", "figma"],
        "practice_task": "Készíts egy Card komponenst.",
        "screenshot": {
            "timestamp": "00:12:30",
            "reason": "Figma Auto Layout panel",
        },
    }

    result = parse_processed_chapter(chapter, payload)

    assert result.summary.startswith("Az oktató")
    assert len(result.key_points) == 2
    assert result.screenshot is not None
    assert result.screenshot.timestamp == "00:12:30"


def test_clamp_screenshot_timestamp_to_chapter_bounds():
    chapter = Chapter(
        index=1,
        title="Teszt",
        start="00:10:00,000",
        end="00:15:00,000",
        text="Teszt szöveg.",
    )

    assert clamp_screenshot_timestamp("00:20:00", chapter) == "00:15:00"
    assert clamp_screenshot_timestamp("00:05:00", chapter) == "00:10:00"
