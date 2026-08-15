from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import rocksmith_cdlc_generator.reviewed_techniques as reviewed_techniques
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


def _source() -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256="1" * 64,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[
                    SourceNoteEvent(
                        start_seconds=1.0,
                        duration_seconds=0.5,
                        midi=43,
                        string_index=0,
                        fret=3,
                        techniques=["palm_mute"],
                        import_confidence=1.0,
                        trust_class=SourceTrustClass.symbolic_verified,
                    )
                ],
            )
        ],
    )


def test_supported_techniques_are_normalized_and_unknown_values_fail() -> None:
    assert reviewed_techniques._normalize_techniques([" Vibrato ", "bend", "bend"]) == [
        "bend",
        "vibrato",
    ]
    with pytest.raises(ValueError, match="Unsupported technique"):
        reviewed_techniques._normalize_techniques(["invented_magic_technique"])


def test_apply_reviewed_techniques_is_source_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source()
    monkeypatch.setattr(
        reviewed_techniques,
        "technique_overrides_for_arrangement",
        lambda *args, **kwargs: {0: ["bend", "vibrato"]},
    )

    copied, applied = reviewed_techniques.apply_reviewed_techniques_to_source(
        Path("."),
        source,
        arrangement="lead",
        source_track_index=2,
    )

    assert applied == {0}
    assert source.tracks[0].notes[0].techniques == ["palm_mute"]
    assert copied.tracks[0].notes[0].techniques == ["bend", "vibrato"]
    assert copied.tracks[0].notes[0].trust_class is SourceTrustClass.symbolic_verified


def test_explicit_acceptance_writes_provenance_bound_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    fanout = project / "sources" / "imported" / "score-fanout.json"
    fanout.parent.mkdir(parents=True)
    fanout.write_text("fanout-authority\n", encoding="utf-8")
    source = _source()
    note = source.tracks[0].notes[0]
    entry = SimpleNamespace(source_track_index=2)
    score = SimpleNamespace(source_sha256="1" * 64, source_format="gp5")

    monkeypatch.setattr(reviewed_techniques, "load_score_for_mapping_review", lambda _project: score)
    monkeypatch.setattr(reviewed_techniques, "_current_fanout", lambda _project: (fanout, object()))
    monkeypatch.setattr(
        reviewed_techniques,
        "_source_event",
        lambda _project, arrangement, event_index: (entry, source.tracks[0], note),
    )
    monkeypatch.setattr(reviewed_techniques, "load_current_reviewed_techniques", lambda _project: None)

    layer = reviewed_techniques.set_reviewed_techniques(
        project,
        arrangement="lead",
        event_index=0,
        techniques=["vibrato", "bend"],
    )

    decision = layer.decision_for("lead", 2, 0)
    assert decision is not None
    assert decision.source_start_seconds == pytest.approx(1.0)
    assert decision.source_duration_seconds == pytest.approx(0.5)
    assert decision.midi == 43
    assert decision.source_techniques == ["palm_mute"]
    assert decision.reviewed_techniques == ["bend", "vibrato"]
    assert layer.fanout_manifest_sha256 == sha256_file(fanout)
    assert (project / reviewed_techniques.TECHNIQUE_REVIEW_PATH).is_file()


def test_empty_reviewed_technique_set_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    assert reviewed_techniques._normalize_techniques([]) == []
    assert reviewed_techniques._normalize_techniques(["", "   "]) == []
