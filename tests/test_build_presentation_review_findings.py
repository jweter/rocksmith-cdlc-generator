from pathlib import Path

import rocksmith_cdlc_generator.dlcbuilder as dlcbuilder_module
from rocksmith_cdlc_generator.build_presentation import save_build_presentation
from rocksmith_cdlc_generator.cli import build_parser
from rocksmith_cdlc_generator.metadata_integration import ResolvedBuildMetadata
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest


def _manifest() -> ProjectManifest:
    return ProjectManifest(
        project_name="song",
        artist="Artist",
        title="Title",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=120.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )


def test_cover_confirmation_preserves_unowned_cover_prefixed_files(tmp_path: Path) -> None:
    project = tmp_path / "song"
    assets = project / "assets"
    assets.mkdir(parents=True)
    license_file = assets / "cover.license"
    original_file = assets / "cover.original.png"
    backup_file = assets / "cover.backup.jpg"
    for path, payload in (
        (license_file, b"license"),
        (original_file, b"original"),
        (backup_file, b"backup"),
    ):
        path.write_bytes(payload)

    source = tmp_path / "selected.png"
    source.write_bytes(b"confirmed")
    save_build_presentation(project, album_name="Album", year=2026, cover=source)

    assert license_file.read_bytes() == b"license"
    assert original_file.read_bytes() == b"original"
    assert backup_file.read_bytes() == b"backup"
    assert (assets / "cover.png").read_bytes() == b"confirmed"


def test_prepare_dlcbuilder_cli_allows_confirmed_cover_fallback() -> None:
    args = build_parser().parse_args(["prepare-dlcbuilder", "project"])

    assert args.command == "prepare-dlcbuilder"
    assert args.cover is None


def test_complete_explicit_presentation_override_does_not_load_saved_state(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "song"
    (project / "audio").mkdir(parents=True)
    (project / "audio" / "normalized.wav").write_bytes(b"audio")
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"cover")
    preview = tmp_path / "preview.wav"
    preview.write_bytes(b"preview")

    monkeypatch.setattr(dlcbuilder_module, "require_configured_arrangements_ready", lambda _: None)
    monkeypatch.setattr(
        dlcbuilder_module,
        "load_build_presentation",
        lambda _: (_ for _ in ()).throw(AssertionError("saved presentation must not be loaded")),
    )
    monkeypatch.setattr(dlcbuilder_module.ProjectManifest, "load", lambda _: _manifest())
    monkeypatch.setattr(dlcbuilder_module, "configured_arrangement_roles", lambda _: [])
    monkeypatch.setattr(
        dlcbuilder_module,
        "resolve_build_metadata",
        lambda *_args, **_kwargs: ResolvedBuildMetadata(
            album_name="Explicit Album",
            year=2026,
            album_source="explicit",
            year_source="explicit",
            selected_metadata_path=None,
            recording_context_path=None,
        ),
    )
    monkeypatch.setattr(
        dlcbuilder_module,
        "build_dlcbuilder_project",
        lambda *_args, **_kwargs: {
            "DLCKey": "Explicit",
            "AlbumArtFile": str(cover),
            "AudioFile": {"Path": str(project / "audio" / "normalized.wav")},
            "AudioPreviewFile": {"Path": str(preview)},
            "Arrangements": [],
        },
    )

    output = dlcbuilder_module.prepare_dlcbuilder_project(
        project,
        album_name="Explicit Album",
        year=2026,
        cover=cover,
        preview=preview,
    )

    assert output == project / "build" / "dlcbuilder" / "Explicit.rs2dlc"
    assert output.is_file()
