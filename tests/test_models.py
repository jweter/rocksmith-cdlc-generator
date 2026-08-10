from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest


def test_manifest_round_trip(tmp_path) -> None:
    manifest = ProjectManifest(
        project_name="Test Artist - Test Song",
        artist="Test Artist",
        title="Test Song",
        arrangement_instruments=["bass"],
        source_original_path="C:/music/test.wav",
        source_project_path="source/test.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=12.5,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )
    manifest.save(tmp_path)
    loaded = ProjectManifest.load(tmp_path)
    assert loaded.source_sha256 == "a" * 64
    assert loaded.arrangement_instruments == ["bass"]
