from pathlib import Path

from rocksmith_cdlc_generator.tone_catalog import (
    BoundRocksmithTone,
    BoundRocksmithTonePlan,
    BoundToneComponent,
)
from rocksmith_cdlc_generator.tone_reference_library import (
    LocalToneReference,
    ReferenceToneComponent,
    ToneReferenceLibrary,
)
from rocksmith_cdlc_generator.tone_reference_recommendations import build_tone_reference_evidence


def _plan() -> BoundRocksmithTonePlan:
    return BoundRocksmithTonePlan(
        artist="Target Artist",
        title="Target Song",
        catalog_sha256="c" * 64,
        tones=[
            BoundRocksmithTone(
                arrangement="lead",
                label="Lead",
                components=[
                    BoundToneComponent(
                        family="amp_high_gain",
                        device_key="amp-match",
                        device_name="Matched Amp",
                        device_type="Amp",
                        slot="Amp",
                        knob_values={"Gain": 0.5},
                        confidence=0.8,
                        reason="synthetic test",
                    )
                ],
            )
        ],
    )


def _reference(
    path: Path,
    *,
    source_type: str = "official_rocksmith",
    arrangement: str = "lead",
    device_key: str = "amp-match",
    tone_key: str = "tone-a",
    knob: float = 0.7,
) -> LocalToneReference:
    return LocalToneReference(
        source_psarc_sha256="1" * 64,
        source_path=str(path),
        source_type=source_type,
        artist="Reference Artist",
        title="Reference Song",
        arrangement=arrangement,
        tone_key=tone_key,
        tone_name="Reference Tone",
        tone_descriptors=["High_Gain"],
        components=[
            ReferenceToneComponent(
                slot="Amp",
                device_key=device_key,
                device_name="Reference Amp",
                device_type="Amp",
                knob_values={"Gain": knob},
            )
        ],
    )


def test_reference_evidence_is_read_only_and_human_gated(tmp_path: Path) -> None:
    plan = _plan()
    original = plan.model_dump()
    library = ToneReferenceLibrary(
        scan_root=str(tmp_path),
        tones=[_reference(tmp_path / "official.psarc")],
    )

    report = build_tone_reference_evidence(plan, library)

    assert plan.model_dump() == original
    assert report.human_review_required is True
    assert report.can_auto_apply is False
    assert report.arrangements[0].human_review_required is True
    assert report.arrangements[0].candidates[0].evidence_only is True
    assert report.arrangements[0].candidates[0].components[0].knob_values == {"Gain": 0.7}
    assert plan.tones[0].components[0].knob_values == {"Gain": 0.5}


def test_reference_evidence_requires_actual_device_overlap(tmp_path: Path) -> None:
    library = ToneReferenceLibrary(
        scan_root=str(tmp_path),
        tones=[_reference(tmp_path / "unrelated.psarc", device_key="different-amp")],
    )

    report = build_tone_reference_evidence(_plan(), library)

    evidence = report.arrangements[0]
    assert evidence.candidates == []
    assert "No local tone reference shared" in evidence.warnings[0]


def test_reference_evidence_keeps_arrangement_roles_isolated(tmp_path: Path) -> None:
    library = ToneReferenceLibrary(
        scan_root=str(tmp_path),
        tones=[
            _reference(tmp_path / "lead.psarc", arrangement="lead"),
            _reference(tmp_path / "bass.psarc", arrangement="bass"),
        ],
    )

    report = build_tone_reference_evidence(_plan(), library)

    assert len(report.arrangements[0].candidates) == 1
    assert report.arrangements[0].candidates[0].source_path.endswith("lead.psarc")


def test_reference_evidence_collapses_duplicate_tone_chains(tmp_path: Path) -> None:
    official = _reference(tmp_path / "official.psarc", source_type="official_rocksmith")
    duplicate = official.model_copy(
        update={
            "source_path": str(tmp_path / "custom.psarc"),
            "source_type": "custom_dlc",
            "tone_key": "tone-duplicate",
        }
    )
    distinct = _reference(
        tmp_path / "distinct.psarc",
        source_type="custom_dlc",
        tone_key="tone-distinct",
        knob=0.8,
    )
    library = ToneReferenceLibrary(scan_root=str(tmp_path), tones=[duplicate, distinct, official])

    report = build_tone_reference_evidence(_plan(), library, limit_per_arrangement=5)

    candidates = report.arrangements[0].candidates
    assert len(candidates) == 2
    assert candidates[0].source_type == "official_rocksmith"
    assert len({item.fingerprint for item in candidates}) == 2


def test_reference_evidence_refuses_unsupported_arrangement_role(tmp_path: Path) -> None:
    plan = _plan().model_copy(deep=True)
    plan.tones[0].arrangement = "combo"
    library = ToneReferenceLibrary(scan_root=str(tmp_path))

    report = build_tone_reference_evidence(plan, library)

    assert report.arrangements[0].candidates == []
    assert "not eligible" in report.arrangements[0].warnings[0]
