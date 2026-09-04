from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pytest
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import register_private_score_bundle
from rocksmith_cdlc_generator.score_measure_recognition import (
    ScoreMeasureRecognitionError,
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


def _clean_response(*, notated_midi: int = 43) -> dict:
    content = {
        "events": [
            {
                "kind": "note",
                "beat": 1,
                "duration_beats": 1,
                "string": 0,
                "fret": 5,
                "notated_midi": notated_midi,
                "techniques": [],
                "confidence": 0.96,
                "ambiguity": None,
            },
            {
                "kind": "rest",
                "beat": 2,
                "duration_beats": 1,
                "string": None,
                "fret": None,
                "notated_midi": None,
                "techniques": [],
                "confidence": 0.92,
                "ambiguity": None,
            },
            {
                "kind": "note",
                "beat": 3,
                "duration_beats": 2,
                "string": 1,
                "fret": 0,
                "notated_midi": 45,
                "techniques": [],
                "confidence": 0.95,
                "ambiguity": None,
            },
        ],
        "confidence": 0.94,
        "ambiguity_notes": [],
    }
    return {"message": {"content": json.dumps(content)}}


def test_candidate_recognition_sends_private_crop_only_to_loopback_and_uses_schema(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    calls: list[tuple[str, dict, float]] = []

    def fake_transport(url: str, payload: dict, timeout: float) -> dict:
        calls.append((url, payload, timeout))
        return _clean_response()

    result = recognize_score_measure_candidates(
        project,
        2,
        model="gemma3:4b",
        limit=1,
        expected_system_count=1,
        transport=fake_transport,
    )

    assert len(result.measures) == 1
    assert result.measures[0].review_required is True
    assert calls and calls[0][0] == "http://127.0.0.1:11434/api/chat"
    payload = calls[0][1]
    assert payload["model"] == "gemma3:4b"
    assert payload["stream"] is False
    assert isinstance(payload["format"], dict)
    encoded = payload["messages"][0]["images"][0]
    assert base64.b64decode(encoded).startswith(b"\x89PNG")


def test_remote_ollama_endpoint_is_rejected_before_private_image_access(tmp_path: Path) -> None:
    with pytest.raises(ScoreMeasureRecognitionError, match="local-only"):
        recognize_score_measure_candidates(
            tmp_path / "does-not-need-to-exist",
            2,
            base_url="https://example.com",
            transport=lambda _url, _payload, _timeout: _clean_response(),
        )


def test_tab_to_notation_pitch_mismatch_is_deterministically_flagged(tmp_path: Path) -> None:
    project = _register_page(tmp_path)

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=lambda _url, _payload, _timeout: _clean_response(notated_midi=44),
    )

    assert any("tab_notation_pitch_mismatch" in warning for warning in result.warnings)


def test_materialized_model_output_remains_blocked_on_human_review(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    candidates = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=lambda _url, _payload, _timeout: _clean_response(),
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


def test_valid_json_wrapped_in_a_single_markdown_fence_is_accepted(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    clean = _clean_response()
    fenced = {"message": {"content": "```json\n" + clean["message"]["content"] + "\n```"}}

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=lambda _url, _payload, _timeout: fenced,
    )

    assert len(result.measures) == 1
    assert result.measures[0].response.events[0].fret == 5


def test_malformed_json_retries_once_and_succeeds_on_second_attempt(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    responses = [
        {"message": {"content": "not json at all"}},
        _clean_response(),
    ]
    calls: list[dict] = []

    def fake_transport(_url: str, payload: dict, _timeout: float) -> dict:
        calls.append(payload)
        return responses[len(calls) - 1]

    result = recognize_score_measure_candidates(
        project,
        2,
        limit=1,
        expected_system_count=1,
        transport=fake_transport,
    )

    assert len(calls) == 2
    assert "did not satisfy the required JSON schema" in calls[1]["messages"][0]["content"]
    assert len(result.measures) == 1


def test_malformed_json_after_retry_raises_measure_specific_sanitized_error(tmp_path: Path) -> None:
    project = _register_page(tmp_path)
    private_marker = "PRIVATE-SCORE-CONTENT-MUST-NOT-LEAK"

    def fake_transport(_url: str, _payload: dict, _timeout: float) -> dict:
        return {"message": {"content": f"garbled non-json output referencing {private_marker}"}}

    with pytest.raises(ScoreMeasureRecognitionError, match=r"after one retry.*measure 1") as excinfo:
        recognize_score_measure_candidates(
            project,
            2,
            limit=1,
            expected_system_count=1,
            transport=fake_transport,
        )

    assert private_marker not in str(excinfo.value)
