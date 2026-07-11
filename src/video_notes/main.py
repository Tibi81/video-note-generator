from __future__ import annotations

from pathlib import Path

import typer
import yaml

from video_notes.ai import SUPPORTED_PROVIDERS, apply_provider_defaults
from video_notes.chapters import detect_chapters, export_chapters_json, load_clean_document
from video_notes.cleaner import clean_document, export_clean_json, load_subtitle_document
from video_notes.models import (
    AIConfig,
    ChaptersConfig,
    CleanerConfig,
    MarkdownConfig,
    ScreenshotsConfig,
)
from video_notes.markdown import build_markdown, export_markdown
from video_notes.parser import export_json, parse_srt_file
from video_notes.pipeline import resolve_input_paths, run_pipeline
from video_notes.screenshots import (
    export_manifest,
    extract_screenshots,
    find_video_file,
    load_manifest,
    load_summary_document,
)
from video_notes.summarize import export_summary_json, load_chapter_document, summarize_document

app = typer.Typer(
    name="video-notes",
    help="Videós workshopok → Obsidian jegyzetek",
    no_args_is_help=True,
)


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("config.yaml")
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def cleaner_config_from_settings(settings: dict) -> CleanerConfig:
    return CleanerConfig.model_validate(settings.get("cleaner", {}))


def chapters_config_from_settings(settings: dict) -> ChaptersConfig:
    return ChaptersConfig.model_validate(settings.get("chapters", {}))


def ai_config_from_settings(settings: dict) -> AIConfig:
    return AIConfig.model_validate(settings.get("ai", {}))


def resolve_ai_config(
    settings: dict,
    provider: str | None = None,
    model: str | None = None,
) -> AIConfig:
    config = ai_config_from_settings(settings)
    return apply_provider_defaults(config, provider=provider, model=model)


def screenshots_config_from_settings(settings: dict) -> ScreenshotsConfig:
    return ScreenshotsConfig.model_validate(settings.get("screenshots", {}))


def markdown_config_from_settings(settings: dict) -> MarkdownConfig:
    return MarkdownConfig.model_validate(settings.get("markdown", {}))


def format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def default_output_dir(settings: dict) -> Path:
    return Path(settings.get("output", {}).get("directory", "output"))


def print_parse_stats(document) -> None:
    stats = document.stats
    if stats is None:
        typer.echo("Nincs statisztika.")
        return

    typer.echo("")
    typer.echo("Parser statisztika")
    typer.echo("-" * 40)
    typer.echo(f"  Forrás:                  {document.source_file}")
    typer.echo(f"  Feliratblokkok:          {stats.entry_count}")
    typer.echo(
        f"  Időtartam:               {format_duration(stats.total_duration_seconds)}"
        f" ({stats.total_duration_seconds:.0f} mp)"
    )
    typer.echo(f"  Szavak:                  {stats.word_count:,}")
    typer.echo(f"  Karakterek:              {stats.char_count:,}")
    typer.echo(f"  Átlag blokk hossz:       {stats.avg_block_duration_seconds:.2f} mp")
    typer.echo(f"  Átlag szó/blokk:         {stats.avg_words_per_block:.2f}")
    typer.echo(f"  Első időbélyeg:          {stats.first_timestamp}")
    typer.echo(f"  Utolsó időbélyeg:        {stats.last_timestamp}")
    typer.echo("")


def print_clean_stats(document) -> None:
    stats = document.stats
    if stats is None:
        typer.echo("Nincs statisztika.")
        return

    typer.echo("")
    typer.echo("Cleaner statisztika")
    typer.echo("-" * 40)
    typer.echo(f"  Forrás:                  {document.source_file}")
    typer.echo(f"  Eredeti blokkok:         {stats.original_entries}")
    typer.echo(f"  Eltávolítva (zaj):       {stats.removed_entries}")
    typer.echo(f"  Tisztított blokkok:      {stats.merged_blocks}")
    typer.echo(f"  Csökkenés:               {stats.reduction_percent:.1f}%")
    typer.echo(
        f"  Időtartam:               {format_duration(stats.total_duration_seconds)}"
        f" ({stats.total_duration_seconds:.0f} mp)"
    )
    typer.echo(f"  Szavak:                  {stats.word_count:,}")
    typer.echo(f"  Karakterek:              {stats.char_count:,}")
    typer.echo(f"  Átlag szó/blokk:         {stats.avg_words_per_block:.2f}")
    typer.echo(f"  Első időbélyeg:          {stats.first_timestamp}")
    typer.echo(f"  Utolsó időbélyeg:        {stats.last_timestamp}")
    typer.echo("")


def print_chapter_stats(document) -> None:
    stats = document.stats
    if stats is None:
        typer.echo("Nincs statisztika.")
        return

    typer.echo("")
    typer.echo("Chapters statisztika")
    typer.echo("-" * 40)
    typer.echo(f"  Forrás:                  {document.source_file}")
    typer.echo(f"  Módszer:                 {stats.method}")
    typer.echo(f"  Szegmensek:              {stats.segment_count}")
    typer.echo(f"  Fejezetek:               {stats.chapter_count}")
    typer.echo(
        f"  Időtartam:               {format_duration(stats.total_duration_seconds)}"
        f" ({stats.total_duration_seconds:.0f} mp)"
    )
    typer.echo(f"  Szavak:                  {stats.word_count:,}")
    typer.echo(f"  Átlag szó/fejezet:       {stats.avg_words_per_chapter:.2f}")
    typer.echo(f"  Átlag fejezet hossz:     {stats.avg_chapter_duration_seconds:.2f} mp")
    typer.echo(f"  Első időbélyeg:          {stats.first_timestamp}")
    typer.echo(f"  Utolsó időbélyeg:        {stats.last_timestamp}")
    typer.echo("")

    for chapter in document.chapters[:10]:
        typer.echo(f"  {chapter.index:02d}. {chapter.start[:8]}  {chapter.title}")
    if len(document.chapters) > 10:
        typer.echo(f"  ... és még {len(document.chapters) - 10} fejezet")
    typer.echo("")


def print_summary_stats(document) -> None:
    stats = document.stats
    if stats is None:
        typer.echo("Nincs statisztika.")
        return

    typer.echo("")
    typer.echo("Summary statisztika")
    typer.echo("-" * 40)
    typer.echo(f"  Forrás:                  {document.source_file}")
    typer.echo(f"  AI provider:             {stats.provider} ({stats.model})")
    typer.echo(f"  Feldolgozott fejezetek:  {stats.processed_count}/{stats.chapter_count}")
    typer.echo(f"  Screenshot javaslatok:   {stats.screenshot_count}")
    typer.echo(f"  Összefoglaló szavak:     {stats.word_count:,}")
    typer.echo("")


@app.command()
def parse(
    subtitle: Path = typer.Argument(
        ...,
        help="SRT feliratfájl elérési útja",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="JSON kimenet elérési útja",
    ),
    stats: bool = typer.Option(
        True,
        "--stats/--no-stats",
        help="Statisztika megjelenítése",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """SRT felirat beolvasása és JSON-ba exportálása."""
    settings = load_config(config)
    encoding = settings.get("parser", {}).get("encoding", "utf-8")

    document = parse_srt_file(subtitle, encoding=encoding)

    if output is None:
        output = default_output_dir(settings) / "parsed.json"

    export_json(document, output)
    typer.echo(f"Exportálva: {output}")

    if stats:
        print_parse_stats(document)


@app.command()
def clean(
    source: Path = typer.Argument(
        ...,
        help="SRT vagy parsed.json fájl",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Tisztított JSON kimenet",
    ),
    stats: bool = typer.Option(
        True,
        "--stats/--no-stats",
        help="Statisztika megjelenítése",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Felirat tisztítása: zaj eltávolítás és blokk összevonás."""
    settings = load_config(config)
    cleaner_config = cleaner_config_from_settings(settings)

    document = load_subtitle_document(source)
    cleaned = clean_document(document, cleaner_config)

    if output is None:
        output = default_output_dir(settings) / "cleaned.json"

    export_clean_json(cleaned, output)
    typer.echo(f"Exportálva: {output}")

    if stats:
        print_clean_stats(cleaned)


@app.command()
def chapters(
    source: Path = typer.Argument(
        ...,
        help="cleaned.json fájl",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Fejezetek JSON kimenet",
    ),
    stats: bool = typer.Option(
        True,
        "--stats/--no-stats",
        help="Statisztika megjelenítése",
    ),
    method: str | None = typer.Option(
        None,
        "--method",
        "-m",
        help="heuristic vagy ai",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"AI provider: {', '.join(SUPPORTED_PROVIDERS)}",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="AI modell neve (pl. mistral-small-latest, gpt-4o)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Tisztított felirat logikus fejezetekre bontása."""
    settings = load_config(config)
    chapters_config = chapters_config_from_settings(settings)
    if method:
        chapters_config.method = method

    cleaned = load_clean_document(source)
    ai_config = None
    if chapters_config.method == "ai":
        try:
            ai_config = resolve_ai_config(settings, provider=provider, model=model)
            typer.echo(
                f"AI provider: {ai_config.provider} ({ai_config.model})"
            )
        except RuntimeError as exc:
            typer.echo(f"Hiba: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    try:
        result = detect_chapters(
            cleaned,
            config=chapters_config,
            ai_config=ai_config,
        )
    except RuntimeError as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output is None:
        output = default_output_dir(settings) / "chapters.json"

    export_chapters_json(result, output)
    typer.echo(f"Exportálva: {output}")

    if stats:
        print_chapter_stats(result)


@app.command()
def summarize(
    source: Path = typer.Argument(
        ...,
        help="chapters.json fájl",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Feldolgozott fejezetek JSON kimenet",
    ),
    stats: bool = typer.Option(
        True,
        "--stats/--no-stats",
        help="Statisztika megjelenítése",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"AI provider: {', '.join(SUPPORTED_PROVIDERS)}",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="AI modell neve",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Fejezetek AI-val történő összefoglalása tanulási jegyzethez."""
    settings = load_config(config)

    try:
        ai_config = resolve_ai_config(settings, provider=provider, model=model)
    except RuntimeError as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"AI provider: {ai_config.provider} ({ai_config.model})")

    chapters_doc = load_chapter_document(source)
    typer.echo(f"Fejezetek feldolgozása: {len(chapters_doc.chapters)} db...")

    try:
        result = summarize_document(
            chapters_doc,
            ai_config=ai_config,
            on_progress=lambda index, total, chapter: typer.echo(
                f"  [{index}/{total}] {chapter.title}"
            ),
        )
    except RuntimeError as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output is None:
        output = default_output_dir(settings) / "summary.json"

    export_summary_json(result, output)
    typer.echo(f"Exportálva: {output}")

    if stats:
        print_summary_stats(result)


@app.command()
def shots(
    source: Path = typer.Argument(
        ...,
        help="summary.json fájl",
        exists=True,
        readable=True,
    ),
    video: Path | None = typer.Option(
        None,
        "--video",
        "-v",
        help="Videófájl elérési útja (auto: input/ mappa)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="screenshots.json manifest",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Screenshotok kivágása a videóból ffmpeg-gel."""
    settings = load_config(config)
    output_dir = default_output_dir(settings)
    screenshots_config = screenshots_config_from_settings(settings)

    summary = load_summary_document(source)
    video_path = video
    if video_path is None:
        input_dir = Path(settings.get("input", {}).get("directory", "input"))
        extensions = settings.get("input", {}).get("video_extensions")
        video_path = find_video_file(input_dir, extensions=extensions)

    typer.echo(f"Videó: {video_path}")
    typer.echo(f"Screenshotok kivágása: {len([c for c in summary.chapters if c.screenshot])} jelölés...")

    try:
        manifest = extract_screenshots(
            summary,
            video_path=video_path,
            output_dir=output_dir,
            config=screenshots_config,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    unique_files = len({record.filename for record in manifest.screenshots})
    manifest_path = output or output_dir / "screenshots.json"
    export_manifest(manifest, manifest_path)

    typer.echo(f"Képek: {output_dir / manifest.images_dir} ({unique_files} fájl)")
    typer.echo(f"Manifest: {manifest_path}")


@app.command()
def build(
    source: Path = typer.Argument(
        ...,
        help="summary.json fájl",
        exists=True,
        readable=True,
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        "-m",
        help="screenshots.json manifest",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Markdown kimenet (notes.md)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Obsidian-kompatibilis Markdown jegyzet generálása."""
    settings = load_config(config)
    output_dir = default_output_dir(settings)
    markdown_config = markdown_config_from_settings(settings)

    summary = load_summary_document(source)
    manifest_path = manifest or output_dir / "screenshots.json"
    screenshots_manifest = None

    if manifest_path.exists():
        screenshots_manifest = load_manifest(manifest_path)
    else:
        typer.echo(f"Figyelmeztetés: nincs manifest ({manifest_path}), képek nélkül készül.")

    content = build_markdown(
        summary,
        manifest=screenshots_manifest,
        config=markdown_config,
    )

    notes_path = output or output_dir / "notes.md"
    export_markdown(content, notes_path)
    typer.echo(f"Exportálva: {notes_path}")
    typer.echo(f"Fejezetek: {len(summary.chapters)}")


@app.command()
def process(
    source: Path = typer.Argument(
        Path("input"),
        help="input/ mappa vagy .srt fájl",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Kimeneti mappa",
    ),
    video: Path | None = typer.Option(
        None,
        "--video",
        "-v",
        help="Videófájl (auto-felismerés input/ mappából)",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"AI provider: {', '.join(SUPPORTED_PROVIDERS)}",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="AI modell neve",
    ),
    skip_summarize: bool = typer.Option(
        False,
        "--skip-summarize",
        help="AI összefoglaló kihagyása (csak parse/clean/chapters)",
    ),
    skip_shots: bool = typer.Option(
        False,
        "--skip-shots",
        help="Screenshot kivágás kihagyása",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="config.yaml elérési útja",
    ),
) -> None:
    """Teljes pipeline egy lepesben: SRT -> Obsidian jegyzet."""
    settings = load_config(config)
    output_dir = output or default_output_dir(settings)

    if not source.exists():
        typer.echo(f"Hiba: a forrás nem található: {source}", err=True)
        raise typer.Exit(code=1)

    try:
        subtitle, detected_video = resolve_input_paths(source, settings)
    except FileNotFoundError as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    video_path = video or detected_video

    typer.echo("Video Note Generator — teljes feldolgozás")
    typer.echo("=" * 40)
    typer.echo(f"  Felirat:  {subtitle}")
    typer.echo(f"  Videó:    {video_path or '(nincs)'}")
    typer.echo(f"  Kimenet:  {output_dir}")
    typer.echo("")

    ai_config = None
    if not skip_summarize:
        try:
            ai_config = resolve_ai_config(settings, provider=provider, model=model)
        except RuntimeError as exc:
            typer.echo(f"Hiba: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    try:
        result_paths = run_pipeline(
            subtitle,
            output_dir,
            video=video_path,
            encoding=settings.get("parser", {}).get("encoding", "utf-8"),
            cleaner_config=cleaner_config_from_settings(settings),
            chapters_config=chapters_config_from_settings(settings),
            ai_config=ai_config,
            screenshots_config=screenshots_config_from_settings(settings),
            markdown_config=markdown_config_from_settings(settings),
            skip_summarize=skip_summarize,
            skip_shots=skip_shots,
            log=typer.echo,
        )
    except RuntimeError as exc:
        typer.echo(f"Hiba: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("")
    typer.echo("Kész!")
    if "notes" in result_paths:
        typer.echo(f"  Obsidian jegyzet: {result_paths['notes']}")
    elif "chapters" in result_paths:
        typer.echo(f"  Fejezetek:        {result_paths['chapters']}")


if __name__ == "__main__":
    app()
