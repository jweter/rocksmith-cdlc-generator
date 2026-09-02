from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Callable, Literal, TypeVar
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
VISION_RECOGNIZER_VERSION = "2"
PRIVATE_RECOGNITION_RELATIVE_PATH = Path("derived") / "printed-score" / "recognition"


class ScoreMeasureRecognitionError(RuntimeError):
    pass


class VisionCandidateEvent(BaseModel):
    """Untrusted reconciled model proposal for one printed musical event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
    """Reconciled TAB + notation response consumed by the existing review UI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    events: list[VisionCandidateEvent]
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_notes: list[str] = Field(default_factory=list)


class VisionTabToken(BaseModel):
    """One fret token read only from the TAB band."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(ge=0.0, le=1.0)
    string: int = Field(ge=0)
    fret: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity: str | None = None


class VisionTabMeasureResponse(BaseModel):
    """TAB-only extraction pass; intentionally contains no rhythm inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    notes: list[VisionTabToken]
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_notes: list[str] = Field(default_factory=list)


class VisionRhythmEvent(BaseModel):
    """Standard-notation-only event; string/fret are intentionally absent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["note", "rest"]
    x: float = Field(ge=0.0, le=1.0)
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    notated_midi: int | None = Field(default=None, ge=0, le=127)
    techniques: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity: str | None = None

    @model_validator(mode="after")
    def rest_fields_are_consistent(self) -> "VisionRhythmEvent":
        if self.kind == "rest":
            if self.notated_midi is not None:
                raise ValueError("rhythm rest must not carry notated_midi")
            if self.techniques:
                raise ValueError("rhythm rest must not carry techniques")
        return self


class VisionRhythmMeasureResponse(BaseModel):
    """Notation-only extraction pass; intentionally contains no TAB inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    events: list[VisionRhythmEvent]
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
RecognitionProgress = Callable[[str], None]
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)


def _emit_progress(progress: RecognitionProgress | None, message: str) -> None:
    if progress is not None:
        progress(message)


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


def _padded_png_base64(crop: Image.Image) -> str:
    grayscale = crop.convert("L")
    padded = Image.new("L", (grayscale.width + 24, grayscale.height + 24), 255)
    padded.paste(grayscale, (12, 12))
    output = BytesIO()
    padded.save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _measure_crop(page: Image.Image, measure: DetectedScoreMeasure) -> Image.Image:
    region = measure.region
    return page.crop((region.x0, region.y0, region.x1, region.y1)).convert("L")


def _measure_png_base64(page: Image.Image, measure: DetectedScoreMeasure) -> str:
    """Backward-compatible whole-measure crop helper used by tests/investigation tooling."""

    return _padded_png_base64(_measure_crop(page, measure))


def _measure_band_png_base64(
    page: Image.Image,
    measure: DetectedScoreMeasure,
    *,
    band: Literal["notation", "tab"],
) -> str:
    crop = _measure_crop(page, measure)
    split = round(crop.height * 0.56)
    overlap = max(6, round(crop.height * 0.04))
    if band == "notation":
        selected = crop.crop((0, 0, crop.width, min(crop.height, split + overlap)))
    else:
        selected = crop.crop((0, max(0, split - overlap), crop.width, crop.height))
    return _padded_png_base64(selected)


def _tab_prompt(*, measure_number: int, tuning_midi: list[int]) -> str:
    tuning_text = ", ".join(str(value) for value in tuning_midi)
    return f"""Read ONLY the tablature band from one electric-bass measure.
This crop is private source material. Extract facts only; do not explain or reproduce it.

Practice measure number: {measure_number}
Four bass strings are indexed LOWEST to HIGHEST starting at 0.
Open-string MIDI pitches low-to-high: [{tuning_text}].
On the printed TAB, the VISUAL TOP line is string 3, then 2, then 1, and the VISUAL BOTTOM line is string 0.

Return EVERY printed fret token in strict left-to-right order, including repeated 0s and repeated frets.
Each printed fret token is one sounded note. Do not infer beat, duration, pitch spelling, or rests here.
For each token, x is the horizontal center of the token normalized from 0.0 at the left crop edge to 1.0 at the right crop edge.
If a fret or string line is unclear, keep the token but lower confidence and describe the ambiguity.
Do not collapse a beamed run into one event and do not summarize repeated notes.
"""


def _rhythm_prompt(
    *,
    measure_number: int,
    numerator: int,
    denominator: int,
    tab_note_count: int,
    retry_for_count: bool = False,
) -> str:
    retry_text = (
        "\nA previous notation pass disagreed with the TAB token count. Re-scan every notehead carefully from left to right."
        if retry_for_count
        else ""
    )
    return f"""Read ONLY the standard-notation staff from one electric-bass measure.
This crop is private source material. Extract facts only; do not explain or reproduce it.

Practice measure number: {measure_number}
Meter: {numerator}/{denominator}
A separate TAB-only pass detected {tab_note_count} printed fret tokens for this same bass part.
Use that number only as a cross-check: do not invent noteheads, but do not omit repeated/beamed noteheads either.{retry_text}

Return every sounded notehead and every EXPLICIT rest in strict left-to-right order.
For each event, x is its horizontal center normalized from 0.0 to 1.0 across this crop.
beat is 1-based within the measure. duration_beats uses the printed meter's denominator beat unit.
For sixteenth-note groups in 4/4, each sixteenth has duration_beats 0.25; preserve every notehead.
For note events, optionally provide notated_midi as an independent pitch cross-check and report only visibly supported techniques.
For rests, notated_midi must be null and techniques must be empty.
If anything is unclear, lower confidence and describe the ambiguity instead of guessing.
"""


def _ollama_payload(
    *,
    model: str,
    image_base64: str,
    prompt: str,
    response_model: type[BaseModel] = VisionMeasureResponse,
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
        "format": response_model.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0},
    }


def _extract_response_content(body: dict) -> str:
    try:
        content = body["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ScoreMeasureRecognitionError("Local Ollama response did not contain message.content") from exc
    if not isinstance(content, str):
        raise ScoreMeasureRecognitionError("Local Ollama response message.content was not text")
    match = _JSON_FENCE.match(content)
    return match.group(1).strip() if match else content.strip()


def _validation_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts: list[str] = []
        for item in exc.errors()[:4]:
            location = ".".join(str(part) for part in item.get("loc", ())) or "<root>"
            parts.append(f"{location}:{item.get('type', 'invalid')}")
        if parts:
            return ", ".join(parts)
    return type(exc).__name__


def _parse_schema_response(body: dict, response_model: type[ResponseModel]) -> ResponseModel:
    content = _extract_response_content(body)
    try:
        return response_model.model_validate_json(content)
    except Exception as exc:
        raise ScoreMeasureRecognitionError(
            f"Local vision model response failed {response_model.__name__}: {_validation_summary(exc)}"
        ) from exc


def _parse_ollama_response(body: dict) -> VisionMeasureResponse:
    """Compatibility parser for existing tests/callers; also accepts a single JSON code fence."""

    return _parse_schema_response(body, VisionMeasureResponse)


def _request_schema_with_retry(
    *,
    post: JsonTransport,
    endpoint: str,
    model: str,
    image_base64: str,
    prompt: str,
    response_model: type[ResponseModel],
    timeout_seconds: float,
    measure_number: int,
    stage: str,
    progress: RecognitionProgress | None,
) -> ResponseModel:
    retry_prompt = (
        prompt
        + "\n\nSTRICT RETRY RULE: Return exactly one JSON object matching the supplied schema. "
        "No Markdown fence, prose, comments, or extra keys. Do not change musical facts merely to satisfy the schema."
    )
    last_error: ScoreMeasureRecognitionError | None = None
    for attempt, current_prompt in enumerate((prompt, retry_prompt), start=1):
        if attempt == 2:
            _emit_progress(
                progress,
                f"Measure {measure_number}: retrying {stage} after malformed structured response…",
            )
        body = post(
            endpoint,
            _ollama_payload(
                model=model,
                image_base64=image_base64,
                prompt=current_prompt,
                response_model=response_model,
            ),
            timeout_seconds,
        )
        try:
            return _parse_schema_response(body, response_model)
        except ScoreMeasureRecognitionError as exc:
            last_error = exc
    assert last_error is not None
    raise ScoreMeasureRecognitionError(
        f"Measure {measure_number} {stage} failed structured recognition after one retry: {last_error}"
    ) from last_error


def _reconcile_staged_measure(
    tab: VisionTabMeasureResponse,
    rhythm: VisionRhythmMeasureResponse,
    *,
    measure_number: int,
) -> VisionMeasureResponse:
    tab_notes = sorted(tab.notes, key=lambda note: note.x)
    rhythm_notes = sorted((event for event in rhythm.events if event.kind == "note"), key=lambda event: event.x)
    rests = sorted((event for event in rhythm.events if event.kind == "rest"), key=lambda event: event.x)

    if not tab_notes:
        raise ScoreMeasureRecognitionError(
            f"Measure {measure_number} TAB pass returned no fret tokens; refusing to create an empty transcription."
        )
    if len(tab_notes) != len(rhythm_notes):
        raise ScoreMeasureRecognitionError(
            f"Measure {measure_number} staged recognition unresolved: TAB found {len(tab_notes)} note tokens "
            f"but notation found {len(rhythm_notes)} sounded notes. No candidates were promoted."
        )

    events: list[tuple[float, VisionCandidateEvent]] = []
    ambiguity_notes = [*tab.ambiguity_notes, *rhythm.ambiguity_notes]
    for tab_note, rhythm_note in zip(tab_notes, rhythm_notes):
        alignment_delta = abs(tab_note.x - rhythm_note.x)
        ambiguity_parts = [part for part in (tab_note.ambiguity, rhythm_note.ambiguity) if part]
        if alignment_delta > 0.16:
            ambiguity_parts.append(f"TAB/notation horizontal alignment differs by {alignment_delta:.3f}")
        events.append(
            (
                rhythm_note.x,
                VisionCandidateEvent(
                    kind="note",
                    beat=rhythm_note.beat,
                    duration_beats=rhythm_note.duration_beats,
                    string=tab_note.string,
                    fret=tab_note.fret,
                    notated_midi=rhythm_note.notated_midi,
                    techniques=list(rhythm_note.techniques),
                    confidence=min(tab_note.confidence, rhythm_note.confidence),
                    ambiguity="; ".join(ambiguity_parts) if ambiguity_parts else None,
                ),
            )
        )
    for rest in rests:
        events.append(
            (
                rest.x,
                VisionCandidateEvent(
                    kind="rest",
                    beat=rest.beat,
                    duration_beats=rest.duration_beats,
                    string=None,
                    fret=None,
                    notated_midi=None,
                    techniques=[],
                    confidence=rest.confidence,
                    ambiguity=rest.ambiguity,
                ),
            )
        )
    events.sort(key=lambda item: item[0])
    return VisionMeasureResponse(
        events=[event for _x, event in events],
        confidence=min(tab.confidence, rhythm.confidence),
        ambiguity_notes=ambiguity_notes,
    )


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
    progress: RecognitionProgress | None = None,
) -> PrintedScoreRecognitionCandidateSet:
    """Generate untrusted candidates using independent TAB and notation passes.

    Private image bytes are allowed to leave the process only to a loopback Ollama endpoint.
    TAB string/fret facts and standard-notation rhythm are read independently, then reconciled
    by left-to-right note order and horizontal position. A note-count disagreement fails closed
    instead of emitting the sparse false transcription seen in the first BWV1007 laptop pass.
    Every resulting candidate remains review-required regardless of model confidence.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    endpoint = _local_ollama_url(base_url)
    bundle = verify_private_score_bundle(project_dir)
    _emit_progress(progress, f"Page {printed_page}: segmenting notation/TAB measure geometry…")
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

    total = len(segmentation.measures)
    if total == 0:
        raise ScoreMeasureRecognitionError(
            f"Page {printed_page}: no measures were segmented; recognition cannot continue."
        )
    _emit_progress(progress, f"Page {printed_page}: segmented {total} measure(s); starting local Ollama recognition…")

    post = transport or _post_json
    recognized: list[RecognizedMeasureCandidate] = []
    with Image.open(derivative) as opened:
        page_image = opened.convert("L")
        for ordinal, measure in enumerate(segmentation.measures, start=1):
            measure_number = measure.measure_index + 1
            _emit_progress(progress, f"Measure {ordinal} of {total}: reading TAB fret tokens…")
            tab_image = _measure_band_png_base64(page_image, measure, band="tab")
            tab = _request_schema_with_retry(
                post=post,
                endpoint=endpoint,
                model=model,
                image_base64=tab_image,
                prompt=_tab_prompt(measure_number=measure_number, tuning_midi=bundle.tuning_midi),
                response_model=VisionTabMeasureResponse,
                timeout_seconds=timeout_seconds,
                measure_number=measure_number,
                stage="TAB pass",
                progress=progress,
            )
            _emit_progress(
                progress,
                f"Measure {ordinal} of {total}: TAB found {len(tab.notes)} note token(s); reading notation rhythm…",
            )
            notation_image = _measure_band_png_base64(page_image, measure, band="notation")
            rhythm = _request_schema_with_retry(
                post=post,
                endpoint=endpoint,
                model=model,
                image_base64=notation_image,
                prompt=_rhythm_prompt(
                    measure_number=measure_number,
                    numerator=time_signature_numerator,
                    denominator=time_signature_denominator,
                    tab_note_count=len(tab.notes),
                ),
                response_model=VisionRhythmMeasureResponse,
                timeout_seconds=timeout_seconds,
                measure_number=measure_number,
                stage="notation pass",
                progress=progress,
            )
            rhythm_note_count = sum(event.kind == "note" for event in rhythm.events)
            if rhythm_note_count != len(tab.notes):
                _emit_progress(
                    progress,
                    f"Measure {ordinal} of {total}: note-count mismatch ({len(tab.notes)} TAB vs {rhythm_note_count} notation); rechecking notation once…",
                )
                rhythm = _request_schema_with_retry(
                    post=post,
                    endpoint=endpoint,
                    model=model,
                    image_base64=notation_image,
                    prompt=_rhythm_prompt(
                        measure_number=measure_number,
                        numerator=time_signature_numerator,
                        denominator=time_signature_denominator,
                        tab_note_count=len(tab.notes),
                        retry_for_count=True,
                    ),
                    response_model=VisionRhythmMeasureResponse,
                    timeout_seconds=timeout_seconds,
                    measure_number=measure_number,
                    stage="notation count recheck",
                    progress=progress,
                )
            _emit_progress(progress, f"Measure {ordinal} of {total}: reconciling TAB positions with notation timing…")
            response = _reconcile_staged_measure(tab, rhythm, measure_number=measure_number)
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
            _emit_progress(progress, f"Measure {ordinal} of {total}: candidate ready; continuing…")

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
    _emit_progress(progress, f"Page {printed_page}: saving {len(recognized)} review-required measure candidate(s)…")
    destination = (
        project_root
        / PRIVATE_RECOGNITION_RELATIVE_PATH
        / f"page-{printed_page:03d}-{segmentation.derivative_sha256[:12]}-candidates.json"
    )
    result.write_json(destination)
    _emit_progress(progress, f"Page {printed_page}: recognition complete; opening human review…")
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
