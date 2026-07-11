from pathlib import Path

from video_notes.models import OutputConfig
from video_notes.workspace import (
    archive_input_files,
    next_batch_id,
    resolve_batch_dir,
    resolve_process_workspace,
)


def test_next_batch_id_starts_at_one(tmp_path: Path):
    output_base = tmp_path / "output"
    processed_base = tmp_path / "processed"
    output_base.mkdir()

    assert next_batch_id(output_base, processed_base) == "001"


def test_next_batch_id_increments_from_existing(tmp_path: Path):
    output_base = tmp_path / "output"
    processed_base = tmp_path / "processed"
    (output_base / "001").mkdir(parents=True)
    (output_base / "002").mkdir(parents=True)
    (processed_base / "001").mkdir(parents=True)

    assert next_batch_id(output_base, processed_base) == "003"


def test_resolve_process_workspace_auto_number(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = OutputConfig(directory="output", processed_directory="processed", auto_number=True)

    output_dir, batch_id = resolve_process_workspace(config)

    assert batch_id == "001"
    assert output_dir == Path("output/001")


def test_resolve_process_workspace_explicit_output(tmp_path: Path):
    config = OutputConfig(auto_number=True)
    explicit = tmp_path / "custom-output"

    output_dir, batch_id = resolve_process_workspace(config, explicit_output=explicit)

    assert output_dir == explicit
    assert batch_id is None


def test_resolve_batch_dir_from_summary_path():
    assert resolve_batch_dir(Path("output/001/summary.json")) == Path("output/001")


def test_archive_input_files_with_batch_id(tmp_path: Path):
    subtitle = tmp_path / "input" / "workshop.srt"
    video = tmp_path / "input" / "workshop.webm"
    subtitle.parent.mkdir(parents=True)
    subtitle.write_text("subtitle", encoding="utf-8")
    video.write_bytes(b"video")

    archive_dir = archive_input_files(
        subtitle,
        video,
        tmp_path / "processed",
        batch_id="004",
    )

    assert archive_dir == tmp_path / "processed" / "004"
    assert (archive_dir / "workshop.srt").exists()
    assert (archive_dir / "workshop.webm").exists()
    assert not subtitle.exists()
    assert not video.exists()
