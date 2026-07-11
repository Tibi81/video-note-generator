from pathlib import Path

from video_notes.models import AIConfig
from video_notes.pipeline import find_subtitle_file, resolve_input_paths, run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


class FakeProvider:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return (
            '{"summary": "Teszt összefoglaló.", "key_points": ["⭐ Egy"], '
            '"keywords": ["teszt"], "practice_task": "Próbáld ki.", '
            '"screenshot": null}'
        )


def test_find_subtitle_file(tmp_path: Path):
    (tmp_path / "video.webm").write_text("x", encoding="utf-8")
    (tmp_path / "workshop.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi", encoding="utf-8")

    found = find_subtitle_file(tmp_path)
    assert found.name == "workshop.srt"


def test_resolve_input_paths_from_directory(tmp_path: Path):
    (tmp_path / "workshop.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi", encoding="utf-8")
    (tmp_path / "workshop.webm").write_bytes(b"video")

    subtitle, video = resolve_input_paths(tmp_path, {})
    assert subtitle.name == "workshop.srt"
    assert video is not None
    assert video.name == "workshop.webm"


def test_run_pipeline_without_ai(tmp_path: Path):
    srt = FIXTURES / "sample.srt"
    output_dir = tmp_path / "output"

    paths = run_pipeline(
        srt,
        output_dir,
        skip_summarize=True,
        log=lambda message: None,
    )

    assert paths["parsed"].exists()
    assert paths["cleaned"].exists()
    assert paths["chapters"].exists()
    assert "summary" not in paths
    assert "notes" not in paths


def test_run_pipeline_with_mock_ai(tmp_path: Path):
    srt = FIXTURES / "sample.srt"
    output_dir = tmp_path / "output"

    from video_notes.models import ProcessedChapter, SummaryDocument, SummaryStats
    import video_notes.pipeline as pipeline_module

    def fake_summarize(document, ai_config, prompts_dir=None, provider=None, prompt_context=None, on_progress=None):
        chapters = [
            ProcessedChapter(
                index=chapter.index,
                title=chapter.title,
                start=chapter.start,
                end=chapter.end,
                summary="Teszt összefoglaló.",
                key_points=["⭐ Egy"],
                keywords=["teszt"],
                practice_task="Próbáld ki.",
            )
            for chapter in document.chapters
        ]
        result = SummaryDocument(source_file=document.source_file, chapters=chapters)
        result.stats = SummaryStats(
            chapter_count=len(chapters),
            processed_count=len(chapters),
            screenshot_count=0,
            provider="test",
            model="test",
            word_count=2,
        )
        return result

    original = pipeline_module.summarize_document
    pipeline_module.summarize_document = fake_summarize
    try:
        paths = run_pipeline(
            srt,
            output_dir,
            ai_config=AIConfig(provider="mistral"),
            skip_shots=True,
            log=lambda message: None,
        )
    finally:
        pipeline_module.summarize_document = original

    assert paths["summary"].exists()
    assert paths["notes"].exists()
