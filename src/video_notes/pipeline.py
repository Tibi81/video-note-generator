from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from video_notes.chapters import detect_chapters, export_chapters_json
from video_notes.cleaner import clean_document, export_clean_json
from video_notes.markdown import build_markdown, export_markdown
from video_notes.models import (
    AIConfig,
    ChaptersConfig,
    CleanerConfig,
    MarkdownConfig,
    ScreenshotsConfig,
)
from video_notes.parser import export_json, parse_srt_file
from video_notes.screenshots import (
    export_manifest,
    extract_screenshots,
    find_video_file,
)
from video_notes.summarize import export_summary_json, summarize_document

LogFn = Callable[[str], None]


def find_subtitle_file(
    directory: Path,
    extensions: list[str] | None = None,
) -> Path:
    allowed = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in (extensions or [".srt", ".vtt"])
    }
    matches = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    ]
    if not matches:
        raise FileNotFoundError(f"Nem található feliratfájl itt: {directory}")
    matches.sort(key=lambda item: item.stat().st_size, reverse=True)
    return matches[0]


def resolve_input_paths(
    source: Path,
    settings: dict,
) -> tuple[Path, Path | None]:
    input_settings = settings.get("input", {})
    video_extensions = input_settings.get("video_extensions")
    subtitle_extensions = input_settings.get("subtitle_extensions")

    if source.is_file():
        subtitle = source
        try:
            video = find_video_file(source.parent, extensions=video_extensions)
        except FileNotFoundError:
            video = None
        return subtitle, video

    if source.is_dir():
        subtitle = find_subtitle_file(source, extensions=subtitle_extensions)
        try:
            video = find_video_file(source, extensions=video_extensions)
        except FileNotFoundError:
            video = None
        return subtitle, video

    raise FileNotFoundError(f"A forrás nem található: {source}")


def run_pipeline(
    source: Path,
    output_dir: Path,
    *,
    video: Path | None = None,
    encoding: str = "utf-8",
    cleaner_config: CleanerConfig | None = None,
    chapters_config: ChaptersConfig | None = None,
    ai_config: AIConfig | None = None,
    screenshots_config: ScreenshotsConfig | None = None,
    markdown_config: MarkdownConfig | None = None,
    skip_summarize: bool = False,
    skip_shots: bool = False,
    prompt_context: dict[str, str] | None = None,
    log: LogFn | None = None,
) -> dict[str, Path]:
    emit = log or print
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    emit("[1/6] Parser — SRT beolvasás...")
    parsed = parse_srt_file(source, encoding=encoding)
    parsed_path = output_dir / "parsed.json"
    export_json(parsed, parsed_path)
    paths["parsed"] = parsed_path
    emit(f"       -> {parsed_path}")

    emit("[2/6] Cleaner — zaj eltávolítás...")
    cleaned = clean_document(parsed, cleaner_config or CleanerConfig())
    cleaned_path = output_dir / "cleaned.json"
    export_clean_json(cleaned, cleaned_path)
    paths["cleaned"] = cleaned_path
    emit(f"       -> {cleaned_path} ({cleaned.stats.merged_blocks if cleaned.stats else 0} blokk)")

    emit("[3/6] Chapters — fejezetek felismerése...")
    chapters_result = detect_chapters(
        cleaned,
        config=chapters_config or ChaptersConfig(),
        ai_config=ai_config if (chapters_config or ChaptersConfig()).method == "ai" else None,
        prompt_context=prompt_context,
    )
    chapters_path = output_dir / "chapters.json"
    export_chapters_json(chapters_result, chapters_path)
    paths["chapters"] = chapters_path
    chapter_count = chapters_result.stats.chapter_count if chapters_result.stats else 0
    emit(f"       -> {chapters_path} ({chapter_count} fejezet)")

    if skip_summarize:
        emit("[4/6] Summarize — kihagyva (--skip-summarize)")
        emit("[5/6] Shots — kihagyva")
        emit("[6/6] Build — kihagyva (nincs summary.json)")
        return paths

    if ai_config is None:
        raise RuntimeError("AI konfiguráció szükséges az összefoglaláshoz.")

    emit(f"[4/6] Summarize — AI összefoglaló ({ai_config.provider}/{ai_config.model})...")
    summary_result = summarize_document(
        chapters_result,
        ai_config=ai_config,
        prompt_context=prompt_context,
        on_progress=lambda index, total, chapter: emit(
            f"       [{index}/{total}] {chapter.title}"
        ),
    )
    summary_path = output_dir / "summary.json"
    export_summary_json(summary_result, summary_path)
    paths["summary"] = summary_path
    emit(f"       -> {summary_path}")

    manifest_path = output_dir / "screenshots.json"
    if skip_shots or video is None:
        reason = "nincs videó" if video is None else "--skip-shots"
        emit(f"[5/6] Shots — kihagyva ({reason})")
    else:
        emit(f"[5/6] Shots — képkivágás ({video.name})...")
        manifest = extract_screenshots(
            summary_result,
            video_path=video,
            output_dir=output_dir,
            config=screenshots_config or ScreenshotsConfig(),
        )
        export_manifest(manifest, manifest_path)
        paths["screenshots"] = manifest_path
        unique_files = len({record.filename for record in manifest.screenshots})
        emit(f"       -> {output_dir / manifest.images_dir} ({unique_files} kep)")

    emit("[6/6] Build — Obsidian Markdown...")
    screenshots_manifest = None
    if manifest_path.exists():
        from video_notes.screenshots import load_manifest

        screenshots_manifest = load_manifest(manifest_path)

    content = build_markdown(
        summary_result,
        manifest=screenshots_manifest,
        config=markdown_config or MarkdownConfig(),
    )
    notes_path = output_dir / "notes.md"
    export_markdown(content, notes_path)
    paths["notes"] = notes_path
    emit(f"       -> {notes_path}")

    return paths
