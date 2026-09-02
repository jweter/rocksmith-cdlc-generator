from __future__ import annotations

import base64
import json
from pathlib import Path
import time

from PIL import Image, ImageDraw
import pytest
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import register_private_score_bundle
from rocksmith_cdlc_generator.score_measure_recognition import (
    ScoreMeasureRecognitionError,
    VisionMeasureResponse,
    _parse_ollama_response,
    materialize_unreviewed_printed_notation_fixture,
    recognize_score_measure_candidates,
)


def _draw_system(draw: ImageDraw.ImageDraw, *, top: int, width: int) -> None:
    left = 90
    right = width - 90
    for y in (top, top + 12, top + 24, top + 36, top + 48):
        draw.line((left, y, right, y), fill="black", width=2)
    for y in (top + 78, top + 92, top + 106, top + 120):
        draw.line((left, y, right, y), fill="black", width=2)
    for x in (180, 650, 1080):
        draw.line((x, top - 3, x, top + 50), fill="black", width=3)
        draw.line((x, top + 75, x, top + 123), fill="black", width=3)
    for x in (300, 780):
        draw.ellipse((x, top + 20, x + 10, top + 28), fill="black")
        draw.line((x + 9, top + 22, x + 9, top - 10), fill="black", width=2)


def _register_page(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    page = source / "page-2.png"
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    _draw_system(draw, top=600, width=image.width)
    image.save(page)

    manifest = {
        "schema_version": 1,
        "bundle_id": "SYNTHETIC_VISION_RECOGNITION",
        "work_title": "Synthetic score",
        "composer": "Test",
        "instrument": "bass",
        "tuning_name": "Drop D",
        "tuning_midi": [38, 45, 50, 55],
        "source_rights_class": "user_owned_local",
        "redistribution_allowed": False,
        "pages": [
            {
                "source_filename": page.name,
                "kind": "score",
                "printed_page": 2,
                "expected_sha256": sha256_file(page),
            }
        ],
        "movements": [
            {
                "movement_id": "prelude",
                "title": "Prelude",
                "start_page": 2,
                "end_page": 2,
                "time_signature": "4/4",
            }
        ],
    }
    manifest_path = tmp_path / "bundle.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    project = tmp_path / "project"
    register_private_score_bundle(project, manifest_path, source)
    (project / "printed-score-project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_id": manifest["bundle_id"],
                "instrument": "bass",
                "movement_id": "prelude",
                "movement_title": "Prelude",
                "start_page": 2,
                "end_page": 2,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return project


def _body(payload: dict, *, fenced: bool = False) -> dict:
    text = json.dumps(payload)
    if fenced:
        text = f"```json\n{text}\n```"
    return {"message": {"content": text}}


def _tab_payload(*, frets: tuple[int, ...] = (5, 0), strings: tuple[int, ...] = (0, 1)) -> dict:
    notes = [
        {
            "x": 0.25 + index * 0.35,
            "string": string,
            "fret": fret,
            "confidence": 0.96,
            "ambiguity": None,
        }
        for index, (string, fret) in enumerate(zip(strings, frets))
    ]
    return {"notes": notes, "confidence": 0.95, "ambiguity_notes": []}


def _rhythm_payload(*, notated_midis: tuple[int, ...] = (43, 45)) -> dict:
    events = [
        {
            "kind": "note",
            "x": 0.25,
            "beat": 1,
            "duration_beats": 1,
            "notated_midi": notated_midis[0],
            "techniques": [],
            "confidence": 0.95,
            "ambiguity": None,
        },
        {
            "kind": "rest",
            "x": 0.45,
            "beat": 2,
            "duration_beats": 1,
            "notated_midi": None,
            "techniques": [],
            "confidence": 0.93,
            "ambiguity": None,
        },
        {
            "kind": "note",
            "x": 0.60,
            "beat": 3,
            "duration_beats": 2,
            "notated_midi": notated_midis[1],
            "techniques": [],
            "confidence": 0.94,
            "ambiguity": None,
        },
    ]
    return {"events": events, "confidence": 0.94, "ambiguity_notes": []}


def _staged_transport(
    calls: list[tuple[str, dict, float]],
    *,
    tab_payload: dict | None = None,
    rhythm_payload: dict | None = None,
    fence_tab: bool = False,
):
    tab_value = tab_payload or _tab_payload()
    rhythm_value = rhythm_payload or _rhythm_payload()

    def transport(url: str, payload: dict, timeout: float) -> dict:
        calls.append((url, payload, timeout))
        schema_title = payload["format"].get("title")
        if schema_title == "VisionTabMeasureResponse":
            return _body(tab_value, fenced=fence_tab)
        if schema_title == "VisionRhythmMeasureResponse":
            return _body(rhythm_value)
        raise AssertionError(f"unexpected schema: {schema_title}")

    return transport


def test_candidate_recognition_uses_separate_tab_and_notation_passes(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []
    progress: list[str] = []

    result = recognize_score_measure_candidates(
        project,
        2,
        model="gemma3:4b",
        limit=1,
        expected_system_count=1,
        transport=_staged_transport(calls),
        progress=progress.append,
    )

    assert len(result.measures) == 1
    assert result.recognizer_version == "2"
    assert result.measures[0].review_required is True
    assert [event.fret for event in result.measures[0].response.events if event.kind == "note"] == [5, 0]
    assert [event.string for event in result.measures[0].response.events if event.kind == "note"] == [0, 1]
    assert len(calls) == 2
    assert all(call[0] == "http://127.0.0.1:11434/api/chat" for call in calls)
    assert [call[1]["format"]["title"] for call in calls] == [
        "VisionTabMeasureResponse",
        "VisionRhythmMeasureResponse",
    ]
    for _url, payload, _timeout in calls:
        assert payload["model"] == "gemma3:4b"
        assert payload["stream"] is False
        encoded = payload["messages"][0]["images"][0]
        assert base64.b64decode(encoded).startswith(b"\x89PNG")
    assert any("Measure 1 of 1: reading TAB" in message for message in progress)
    assert any("recognition complete" in message for message in progress)


def test_dense_sixteenth_measure_preserves_all_tab_tokens(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    frets = (5, 0, 4, 7, 4, 0, 4, 0, 5, 0, 4, 7, 4, 0, 4, 0)
    strings = (0, 1, 2, 1, 2, 1, 2, 1, 0, 1, 2, 1, 2, 1, 2, 1)
    tab = {
        "notes": [
            {
                "x": 0.08 + index * 0.052,
                "string": string,
                "fret": fret,
                "confidence": 0.95,
                "ambiguity": None,
            }
            for index, (string, fret) in enumerate(zip(strings, frets))
        ],
        "confidence": 0.95,
        "ambiguity_notes": [],
    }
    rhythm = {
        "events": [
            {
                "kind": "note",
                "x": 0.08 + index * 0.052,
                "beat": 1 + index * 0.25,
                "duration_beats": 0.25,
                "notated_midi": None,
                "techniques": [],
                "confidence": 0.94,
                "ambiguity": None,
            }
            for index in range(16)
        ],
        "confidence": 0.94,
        "ambiguity_notes": [],
    }
    calls: list[tuple[str, dict, float]] = []

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=_staged_transport(calls, tab_payload=tab, rhythm_payload=rhythm),
    )

    notes = [event for event in result.measures[0].response.events if event.kind == "note"]
    assert len(notes) == 16
    assert [event.fret for event in notes] == list(frets)
    assert all(event.duration_beats == 0.25 for event in notes)
    assert not any("measure_coverage_mismatch" in warning for warning in result.warnings)


def test_single_json_code_fence_is_accepted_without_schema_relaxation(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=_staged_transport(calls, fence_tab=True),
    )

    assert len(result.measures) == 1
    assert len(calls) == 2


def test_malformed_structured_response_retries_once_then_succeeds(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []
    tab_attempts = 0

    def transport(url: str, payload: dict, timeout: float) -> dict:
        nonlocal tab_attempts
        calls.append((url, payload, timeout))
        title = payload["format"].get("title")
        if title == "VisionTabMeasureResponse":
            tab_attempts += 1
            if tab_attempts == 1:
                return _body({"notes": "not-a-list", "confidence": 0.9, "ambiguity_notes": []})
            return _body(_tab_payload())
        return _body(_rhythm_payload())

    progress: list[str] = []
    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=transport,
        progress=progress.append,
    )

    assert len(result.measures) == 1
    assert tab_attempts == 2
    assert any("retrying TAB pass" in message for message in progress)


def test_malformed_structured_response_exhaustion_names_measure_and_stage(tmp_path: Path) -> None:
    project = _register_page(tmp_path)

    def transport(_url: str, payload: dict, _timeout: float) -> dict:
        if payload["format"].get("title") == "VisionTabMeasureResponse":
            return _body({"notes": "bad", "confidence": 0.9, "ambiguity_notes": []})
        return _body(_rhythm_payload())

    with pytest.raises(ScoreMeasureRecognitionError, match=r"Measure 1 TAB pass failed"):
        recognize_score_measure_candidates(
            project,
            2,
            limit=1,
            expected_system_count=1,
            transport=transport,
        )


def test_transport_timeout_names_measure_and_stage(tmp_path: Path) -> None:
    project = _register_page(tmp_path)

    def transport(_url: str, payload: dict, timeout: float) -> dict:
        if payload["format"].get("title") == "VisionTabMeasureResponse":
            raise ScoreMeasureRecognitionError(
                f"Local Ollama request timed out after {timeout:g}s waiting for a response."
            )
        return _body(_rhythm_payload())

    with pytest.raises(
        ScoreMeasureRecognitionError,
        match=r"Measure 1 TAB pass request failed: Local Ollama request timed out after 180s",
    ):
        recognize_score_measure_candidates(
            project,
            2,
            limit=1,
            expected_system_count=1,
            transport=transport,
        )


def test_slow_transport_emits_periodic_heartbeat_with_elapsed_time(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []

    def slow_transport(url: str, payload: dict, timeout: float) -> dict:
        if payload["format"].get("title") == "VisionTabMeasureResponse":
            time.sleep(0.12)
        return _staged_transport(calls)(url, payload, timeout)

    progress: list[str] = []
    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=slow_transport,
        progress=progress.append,
        heartbeat_seconds=0.03,
    )

    assert len(result.measures) == 1
    heartbeats = [message for message in progress if "still waiting for TAB pass response" in message]
    assert len(heartbeats) >= 2
    assert any("elapsed" in message for message in heartbeats)


def test_heartbeat_disabled_when_heartbeat_seconds_is_zero(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []

    def slow_transport(url: str, payload: dict, timeout: float) -> dict:
        if payload["format"].get("title") == "VisionTabMeasureResponse":
            time.sleep(0.12)
        return _staged_transport(calls)(url, payload, timeout)

    progress: list[str] = []
    recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=slow_transport,
        progress=progress.append,
        heartbeat_seconds=0,
    )

    assert not any("still waiting for" in message for message in progress)


def test_note_count_mismatch_rechecks_notation_then_fails_closed(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    rhythm = _rhythm_payload()
    rhythm["events"] = rhythm["events"][:1]
    calls: list[tuple[str, dict, float]] = []

    with pytest.raises(ScoreMeasureRecognitionError, match=r"Measure 1 staged recognition unresolved"):
        recognize_score_measure_candidates(
            project,
            2,
            limit=1,
            expected_system_count=1,
            transport=_staged_transport(calls, rhythm_payload=rhythm),
        )

    assert [call[1]["format"]["title"] for call in calls].count("VisionRhythmMeasureResponse") == 2


def test_remote_ollama_endpoint_is_rejected_before_private_image_access(tmp_path: Path) -> None:
    with pytest.raises(ScoreMeasureRecognitionError, match="local-only"):
        recognize_score_measure_candidates(
            tmp_path / "does-not-need-to-exist",
            2,
            base_url="https://example.com",
            transport=lambda _url, _payload, _timeout: _body({}),
        )


def test_tab_to_notation_pitch_mismatch_is_deterministically_flagged(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=_staged_transport(calls, rhythm_payload=_rhythm_payload(notated_midis=(44, 45))),
    )

    assert any("tab_notation_pitch_mismatch" in warning for warning in result.warnings)


def test_materialized_model_output_remains_blocked_on_human_review(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []
    candidates = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=_staged_transport(calls),
    )

    fixture = materialize_unreviewed_printed_notation_fixture(candidates, bpm=80.0)

    page = fixture.pages[0]
    assert len(page.events) == 2
    assert len(page.rests) == 1
    assert all(event.review_required for event in page.events)
    assert all(not event.human_reviewed for event in page.events)
    assert all(rest.review_required for rest in page.rests)
    assert all(not rest.human_reviewed for rest in page.rests)
    assert fixture.tuning_midi == [38, 45, 50, 55]
    assert fixture.bpm == 80.0


def test_legacy_reconciled_parser_still_accepts_valid_response() -> None:
    body = _body(
        {
            "events": [
                {
                    "kind": "note",
                    "beat": 1,
                    "duration_beats": 1,
                    "string": 0,
                    "fret": 5,
                    "notated_midi": 43,
                    "techniques": [],
                    "confidence": 0.95,
                    "ambiguity": None,
                }
            ],
            "confidence": 0.95,
            "ambiguity_notes": [],
        },
        fenced=True,
    )
    parsed = _parse_ollama_response(body)
    assert isinstance(parsed, VisionMeasureResponse)
    assert parsed.events[0].fret == 5
