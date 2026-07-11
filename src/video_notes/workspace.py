from __future__ import annotations

import re
import shutil
from pathlib import Path

from video_notes.models import OutputConfig

_NUMBERED_DIR = re.compile(r"^\d+$")


def next_batch_id(
    *directories: Path,
    padding: int = 3,
) -> str:
    """Következő számozott köteg azonosító (output/ és processed/ mappák alapján)."""
    max_number = 0
    for directory in directories:
        if not directory.exists():
            continue
        for child in directory.iterdir():
            if child.is_dir() and _NUMBERED_DIR.fullmatch(child.name):
                max_number = max(max_number, int(child.name))
    return str(max_number + 1).zfill(padding)


def resolve_process_workspace(
    output_config: OutputConfig,
    *,
    explicit_output: Path | None = None,
) -> tuple[Path, str | None]:
    """Feldolgozáshoz kimeneti mappa és opcionális kötegszám."""
    output_base = Path(output_config.directory)
    processed_base = Path(output_config.processed_directory)

    if explicit_output is not None:
        return explicit_output, None

    if not output_config.auto_number:
        return output_base, None

    batch_id = next_batch_id(
        output_base,
        processed_base,
        padding=output_config.number_padding,
    )
    return output_base / batch_id, batch_id


def archive_input_files(
    subtitle: Path,
    video: Path | None,
    processed_base: Path,
    batch_id: str | None,
) -> Path:
    """Feldolgozott forrásfájlok áthelyezése archív mappába."""
    if batch_id is not None:
        archive_dir = processed_base / batch_id
    else:
        archive_dir = processed_base / subtitle.stem

    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []

    for source in (subtitle, video):
        if source is None or not source.exists():
            continue
        destination = archive_dir / source.name
        if destination.exists():
            destination.unlink()
        shutil.move(str(source), str(destination))
        moved.append(destination)

    if not moved:
        raise RuntimeError("Nem sikerült archiválni a forrásfájlokat.")

    return archive_dir
