from __future__ import annotations

from pathlib import Path

import typer
import yaml

from video_notes.cleaner import clean_document, export_clean_json, load_subtitle_document
from video_notes.models import CleanerConfig
from video_notes.parser import export_json, parse_srt_file

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


if __name__ == "__main__":
    app()
