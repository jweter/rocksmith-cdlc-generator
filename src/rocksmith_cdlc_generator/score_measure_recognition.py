from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .hashing import sha256_file
from .private_score_bundle import verify_private_score_bundle
from .printed_notation_import import (
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationPage,
    PrintedNotationRestEvent,
    PrintedNotationTimeSignature,
)
from .score_measure_segmentation import (
    DetectedScoreMeasure,
    ScoreMeasureSegmentation,
    segment_score_measures,
)


VISION_RECOGNIZER_ID = "ollama-local-printed-score-candidate-recognizer"
VISION_RECOGNIZER_VERSION = "1"
PRIVATE_RECOGNITION_RELATIVE_PATH = Path("derived") / "printed-score" / "recognition"


class ScoreMeasureRecognitionError(RuntimeError):
    pass


class VisionCandidateEvent(BaseModel):
    """Untrusted model proposal for one printed musical event."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["note", "rest"]
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    string: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    notated_midi: int | None = Field(default=None, ge=0, le=127)
    techniques: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity: str | None = None

    @model_validator(mode="after")
    def note_and_rest_fields_are_consistent(self) -> "VisionCandidateEvent":
        if self.kind == "note":
            if self.string is None or self.fret is None:
                raise ValueError("note candidate requires string and fret")
        else:
            if self.string is not None or self.fret is not None:
                raise ValueError("rest candidate must not carry string/fret")
            if self.techniques:
                raise ValueError("rest candidate must not carry note techniques")
        return self


class VisionMeasureResponse(BaseModel):
    """Schema-constrained content returned by a local vision model for one measure."""

    model_config = ConfigDict(frozen=True)

    events: list[VisionCandidateEvent]
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_notes: list[str] = Field(default_factory=list)


class RecognizedMeasureCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    system_index: int = Field(ge=0)
    region: tuple[int, int, int, int]
    geometry_confidence: float = Field(ge=0.0, le=1.0)
    geometry_review_required: bool
    response: VisionMeasureResponse
    deterministic_warnings: list[str] = Field(default_factory=list)
    review_required: bool = True


class PrintedScoreRecognitionCandidateSet(BaseModel):
    """Private, untrusted recognition result bound to exact page/derivative identity."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    recognizer_id: Literal["ollama-local-printed-score-candidate-recognizer"] = VISION_RECOGNIZER_ID
    recognizer_version: str = VISION_RECOGNIZER_VERSION
    model: str
    bundle_id: str
    printed_page: int = Field(ge=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_relative_path: str
    tuning_midi: list[int]
    time_signature_numerator: int = Field(ge=1)
    time_signature_denominator: int = Field(ge=1)
    measures: list[RecognizedMeasureCandidate]
    warnings: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


JsonTransport = Callable[[str, dict, float], dict]


def _local_ollama_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ScoreMeasureRecognitionError("Ollama base URL must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ScoreMeasureRecognitionError(
            "Printed score image recognition is local-only; refusing to send a private score "
            f"crop to non-loopback host {parsed.hostname!r}."
        )
    return base_url.rstrip("/") + "/api/chat"


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ScoreMeasureRecognitionError(
            f"Local Ollama request failed with HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except URLError as exc:
        raise ScoreMeasureRecognitionError(
            "Could not reach local Ollama. Start Ollama and confirm the configured vision model "
            "is installed before running printed-score recognition."
        ) from exc


def _measure_png_base64(page: Image.Image, measure: DetectedScoreMeasure) -> str:
    region = measure.region
    crop = page.crop((region.x0, region.y0, region.x1, region.y1)).convert("L")
    # Add a white margin so symbols touching the detected barline are not clipped by the
    # vision model's preprocessing.
    padded = Image.new("L", (crop.width + 24, crop.height + 24), 255)
    padded.paste(crop, (12, 12))
    output = BytesIO()
    padded.save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _recognition_prompt(
    *,
    measure_number: int,
    numerator: int,
    denominator: int,
    tuning_midi: list[int],
) -> str:
    tuning_text = ", ".join(str(value) for value in tuning_midi)
    return f"""You are reading ONE cropped measure from professionally printed electric-bass music.
The upper staff is standard notation and the lower staff is tablature for the SAME bass part.
This crop is private source material. Extract facts only; do not explain or reproduce the image.

Practice measure number: {measure_number}
Meter: {numerator}/{denominator}
Bass strings are indexed LOWEST to HIGHEST starting at 0.
Open-string MIDI pitches low-to-high: [{tuning_text}].

Return every sounded note and every EXPLICIT rest in left-to-right musical order.
For a note, read the TAB string and fret exactly. Use standard notation to infer beat position,
rhythmic duration, and optionally notated_midi as an independent cross-check. If a symbol is
unclear, lower confidence and describe the ambiguity; never invent a value merely to fill time.
For a rest, set string/fret/notated_midi to null and techniques to an empty list.
beat is 1-based within the measure. duration_beats uses the printed meter's denominator beat unit.
Only report techniques visibly supported by the crop.
"""


_STRICT_SCHEMA_RETRY_SUFFIX = """

Your previous response did not satisfy the required JSON schema. Return ONLY one JSON
object that exactly matches the schema. Do not use Markdown code fences, prose, or any
text outside the JSON object.
"""


def _ollama_payload(
    *,
    model: str,
    image_base64: str,
    prompt: str,
) -> dict:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "format": VisionMeasureResponse.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0},
    }


class _OllamaSchemaValidationError(RuntimeError):
    """Content was extracted but failed strict schema validation.

    Carries only a sanitized summary (field paths/error types) so callers can retry or
    report without reproducing private score content that may appear inside a malformed
    model response.
    """

    def __init__(self, summary: str) -> None:
        super().__init__(summary)
        self.summary = summary


_MARKDOWN_JSON_FENCE_LANGS = ("", "json")


def _strip_single_markdown_json_fence(content: str) -> str | None:
    """Return the inner body if `content` is exactly one ``` ... ``` fenced block.

    This tolerates harmless transport/formatting drift (a model wrapping an otherwise
    valid JSON object in a Markdown code fence) without loosening the schema itself.
    """
    stripped = content.strip()
    if not stripped.startswith("```") or not stripped.endswith("```") or len(stripped) < 6:
        return None
    lines = stripped.splitlines()
    if len(lines) < 3:
        return None
    if lines[0][3:].strip().lower() not in _MARKDOWN_JSON_FENCE_LANGS:
        return None
    if lines[-1].strip() != "```":
        return None
    body = "\n".join(lines[1:-1]).strip()
    return body or None


def _sanitize_schema_failure(exc: Exception, *, measure_number: int) -> str:
    """Summarize a validation failure without echoing the untrusted response content."""
    if isinstance(exc, ValidationError):
        locations = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
            locations.append(f"{loc}:{error.get('type', 'invalid')}")
        detail = ", ".join(locations) if locations else "unspecified schema violation"
    else:
        detail = "content was not valid JSON"
    return f"measure {measure_number}: {detail}"


def _parse_ollama_response(body: dict, *, measure_number: int) -> VisionMeasureResponse:
    try:
        content = body["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ScoreMeasureRecognitionError("Local Ollama response did not contain message.content") from exc
    try:
        return VisionMeasureResponse.model_validate_json(content)
    except Exception as direct_exc:
        fenced = _strip_single_markdown_json_fence(content)
        if fenced is None:
            raise _OllamaSchemaValidationError(
                _sanitize_schema_failure(direct_exc, measure_number=measure_number)
            ) from direct_exc
        try:
            return VisionMeasureResponse.model_validate_json(fenced)
        except Exception as fenced_exc:
            raise _OllamaSchemaValidationError(
                _sanitize_schema_failure(fenced_exc, measure_number=measure_number)
            ) from fenced_exc


def _interval_coverage(events: list[VisionCandidateEvent]) -> float:
    intervals = sorted((event.beat - 1.0, event.beat - 1.0 + event.duration_beats) for event in events)
    merged: list[list[float]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 1e-9:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


def _deterministic_warnings(
    response: VisionMeasureResponse,
    *,
    tuning_midi: list[int],
    numerator: int,
) -> list[str]:
    warnings: list[str] = []
    if not response.events:
        warnings.append("vision_returned_no_events")
        return warnings

    for index, event in enumerate(response.events):
        end_beat = event.beat - 1.0 + event.duration_beats
        if end_beat > numerator + 1e-6:
            warnings.append(
                f"event_{index}:extends_past_measure:end={end_beat:g},limit={numerator}"
            )
        if event.confidence < 0.80:
            warnings.append(f"event_{index}:low_model_confidence={event.confidence:.3f}")
        if event.ambiguity:
            warnings.append(f"event_{index}:model_reported_ambiguity")
        if event.kind == "note":
            assert event.string is not None and event.fret is not None
            if event.string >= len(tuning_midi):
                warnings.append(
                    f"event_{index}:string_out_of_range={event.string};strings={len(tuning_midi)}"
                )
                continue
            tab_midi = tuning_midi[event.string] + event.fret
            if event.notated_midi is not None and tab_midi != event.notated_midi:
                warnings.append(
                    f"event_{index}:tab_notation_pitch_mismatch:tab_midi={tab_midi},"
                    f"notated_midi={event.notated_midi}"
                )

    coverage = _interval_coverage(response.events)
    if abs(coverage - numerator) > 1e-6:
        warnings.append(
            f"measure_coverage_mismatch:coverage={coverage:g},expected={numerator}"
        )
    return warnings


def recognize_score_measure_candidates(
    project_dir: Path,
    printed_page: int,
    *,
    model: str = "gemma3:4b",
    limit: int = 8,
    time_signature_numerator: int = 4,
    time_signature_denominator: int = 4,
    expected_system_count: int | None = None,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 180.0,
    transport: JsonTransport | None = None,
) -> PrintedScoreRecognitionCandidateSet:
    """Generate untrusted local-vision candidates for the first printed score measures.

    Private image bytes are allowed to leave the process only to a loopback Ollama endpoint.
    Every candidate remains review-required regardless of model confidence.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    endpoint = _local_ollama_url(base_url)
    bundle = verify_private_score_bundle(project_dir)
    segmentation: ScoreMeasureSegmentation = segment_score_measures(
        project_dir,
        printed_page,
        limit=limit,
        expected_system_count=expected_system_count,
    )

    project_root = Path(project_dir).expanduser().resolve()
    derivative = (project_root / segmentation.derivative_relative_path).resolve()
    if not derivative.is_relative_to(project_root) or not derivative.is_file():
        raise ScoreMeasureRecognitionError("Normalized score derivative is unavailable")
    if sha256_file(derivative) != segmentation.derivative_sha256:
        raise ScoreMeasureRecognitionError("Normalized score derivative changed before recognition")

    post = transport or _post_json
    recognized: list[RecognizedMeasureCandidate] = []
    with Image.open(derivative) as opened:
        page_image = opened.convert("L")
        for measure in segmentation.measures:
            image_base64 = _measure_png_base64(page_image, measure)
            prompt = _recognition_prompt(
                measure_number=measure.measure_index + 1,
                numerator=time_signature_numerator,
                denominator=time_signature_denominator,
                tuning_midi=bundle.tuning_midi,
            )
            measure_number = measure.measure_index + 1
            body = post(
                endpoint,
                _ollama_payload(model=model, image_base64=image_base64, prompt=prompt),
                timeout_seconds,
            )
            try:
                response = _parse_ollama_response(body, measure_number=measure_number)
            except _OllamaSchemaValidationError:
                retry_body = post(
                    endpoint,
                    _ollama_payload(
                        model=model,
                        image_base64=image_base64,
                        prompt=prompt + _STRICT_SCHEMA_RETRY_SUFFIX,
                    ),
                    timeout_seconds,
                )
                try:
                    response = _parse_ollama_response(retry_body, measure_number=measure_number)
                except _OllamaSchemaValidationError as retry_failure:
                    raise ScoreMeasureRecognitionError(
                        "Local vision model returned content that did not satisfy the "
                        f"recognition schema after one retry ({retry_failure.summary})"
                    ) from retry_failure
            deterministic = _deterministic_warnings(
                response,
                tuning_midi=bundle.tuning_midi,
                numerator=time_signature_numerator,
            )
            recognized.append(
                RecognizedMeasureCandidate(
                    measure_index=measure.measure_index,
                    system_index=measure.system_index,
                    region=(
                        measure.region.x0,
                        measure.region.y0,
                        measure.region.x1,
                        measure.region.y1,
                    ),
                    geometry_confidence=measure.confidence,
                    geometry_review_required=measure.review_required,
                    response=response,
                    deterministic_warnings=deterministic,
                    review_required=True,
                )
            )

    warnings = list(segmentation.warnings)
    warnings.extend(
        f"measure_{measure.measure_index}:{warning}"
        for measure in recognized
        for warning in measure.deterministic_warnings
    )
    result = PrintedScoreRecognitionCandidateSet(
        model=model,
        bundle_id=bundle.bundle_id,
        printed_page=printed_page,
        source_sha256=segmentation.source_sha256,
        derivative_sha256=segmentation.derivative_sha256,
        derivative_relative_path=segmentation.derivative_relative_path,
        tuning_midi=list(bundle.tuning_midi),
        time_signature_numerator=time_signature_numerator,
        time_signature_denominator=time_signature_denominator,
        measures=recognized,
        warnings=warnings,
    )
    destination = (
        project_root
        / PRIVATE_RECOGNITION_RELATIVE_PATH
        / f"page-{printed_page:03d}-{segmentation.derivative_sha256[:12]}-candidates.json"
    )
    result.write_json(destination)
    return result


def materialize_unreviewed_printed_notation_fixture(
    candidates: PrintedScoreRecognitionCandidateSet,
    *,
    bpm: float,
) -> PrintedNotationFixture:
    """Convert model proposals into a fixture that is explicitly blocked on human review."""

    note_events: list[PrintedNotationEvent] = []
    rest_events: list[PrintedNotationRestEvent] = []
    for measure in candidates.measures:
        canonical_measure = measure.measure_index + 1
        for event in measure.response.events:
            confidence = {
                "vision": event.confidence,
                "rhythm": event.confidence,
            }
            if event.kind == "note":
                assert event.string is not None and event.fret is not None
                confidence["fret"] = event.confidence
                note_events.append(
                    PrintedNotationEvent(
                        measure=canonical_measure,
                        beat=event.beat,
                        duration_beats=event.duration_beats,
                        string=event.string,
                        fret=event.fret,
                        techniques=list(event.techniques),
                        field_confidence=confidence,
                        review_required=True,
                        region=measure.region,
                        human_reviewed=False,
                    )
                )
            else:
                confidence["rest"] = event.confidence
                rest_events.append(
                    PrintedNotationRestEvent(
                        measure=canonical_measure,
                        beat=event.beat,
                        duration_beats=event.duration_beats,
                        field_confidence=confidence,
                        review_required=True,
                        region=measure.region,
                        human_reviewed=False,
                    )
                )

    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=list(candidates.tuning_midi),
        bpm=bpm,
        time_signature=PrintedNotationTimeSignature(
            numerator=candidates.time_signature_numerator,
            denominator=candidates.time_signature_denominator,
        ),
        pages=[
            PrintedNotationPage(
                page_number=candidates.printed_page,
                events=note_events,
                rests=rest_events,
            )
        ],
    )
