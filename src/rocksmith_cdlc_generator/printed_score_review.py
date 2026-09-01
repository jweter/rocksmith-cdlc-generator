from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .printed_notation_import import (
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationPage,
    PrintedNotationRestEvent,
    PrintedNotationTimeSignature,
)
from .score_measure_recognition import (
    PRIVATE_RECOGNITION_RELATIVE_PATH,
    PrintedScoreRecognitionCandidateSet,
    VisionCandidateEvent,
)


PRIVATE_REVIEW_RELATIVE_PATH = Path("derived") / "printed-score" / "review"
ReviewStatus = Literal["pending", "approved", "corrected"]
ReviewAction = Literal["approved", "corrected", "added"]


class PrintedScoreReviewError(RuntimeError):
    pass


class ReviewedScoreEvent(BaseModel):
    """One event in the human-edited final interpretation of a measure."""

    model_config = ConfigDict(frozen=True)

    source_event_index: int | None = Field(default=None, ge=0)
    action: ReviewAction
    kind: Literal["note", "rest"]
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    string: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    original_vision_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def note_and_rest_fields_are_consistent(self) -> "ReviewedScoreEvent":
        if self.kind == "note":
            if self.string is None or self.fret is None:
                raise ValueError("reviewed note requires string and fret")
        else:
            if self.string is not None or self.fret is not None:
                raise ValueError("reviewed rest must not carry string/fret")
            if self.techniques:
                raise ValueError("reviewed rest must not carry note techniques")
        if self.action == "added" and self.source_event_index is not None:
            raise ValueError("added event must not reference a source event index")
        return self


class ReviewedScoreMeasure(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    system_index: int = Field(ge=0)
    region: tuple[int, int, int, int]
    status: ReviewStatus = "pending"
    events: list[ReviewedScoreEvent] = Field(default_factory=list)
    discarded_source_event_indexes: list[int] = Field(default_factory=list)
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def discarded_indexes_are_unique(self) -> "ReviewedScoreMeasure":
        if len(set(self.discarded_source_event_indexes)) != len(self.discarded_source_event_indexes):
            raise ValueError("discarded source event indexes must be unique")
        present = {
            event.source_event_index
            for event in self.events
            if event.source_event_index is not None
        }
        if present.intersection(self.discarded_source_event_indexes):
            raise ValueError("an event cannot be both retained and discarded")
        return self


class PrintedScoreReviewRecord(BaseModel):
    """Transactional human-review state bound to one exact candidate JSON file."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    candidate_file_relative_path: str
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_id: str
    printed_page: int = Field(ge=1)
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str
    tuning_midi: list[int]
    time_signature_numerator: int = Field(ge=1)
    time_signature_denominator: int = Field(ge=1)
    candidate_warnings: list[str] = Field(default_factory=list)
    measures: list[ReviewedScoreMeasure]

    @model_validator(mode="after")
    def measure_indexes_are_unique_and_ordered(self) -> "PrintedScoreReviewRecord":
        indexes = [measure.measure_index for measure in self.measures]
        if len(set(indexes)) != len(indexes):
            raise ValueError("review measure indexes must be unique")
        if indexes != sorted(indexes):
            raise ValueError("review measures must remain in reading order")
        return self

    @property
    def all_measures_reviewed(self) -> bool:
        return bool(self.measures) and all(measure.status != "pending" for measure in self.measures)

    @classmethod
    def read_json(cls, path: Path) -> "PrintedScoreReviewRecord":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _project_path(project_dir: Path, path: Path) -> Path:
    root = Path(project_dir).expanduser().resolve()
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise PrintedScoreReviewError("private review path escaped the project directory")
    return candidate


def _atomic_write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def load_candidate_set(
    project_dir: Path,
    candidate_path: Path,
) -> tuple[PrintedScoreRecognitionCandidateSet, Path, str]:
    project_root = Path(project_dir).expanduser().resolve()
    path = _project_path(project_root, candidate_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    candidates = PrintedScoreRecognitionCandidateSet.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    return candidates, path, sha256_file(path)


def _draft_event(index: int, event: VisionCandidateEvent) -> ReviewedScoreEvent:
    return ReviewedScoreEvent(
        source_event_index=index,
        action="approved",
        kind=event.kind,
        beat=event.beat,
        duration_beats=event.duration_beats,
        string=event.string,
        fret=event.fret,
        techniques=list(event.techniques),
        original_vision_confidence=event.confidence,
    )


def create_review_draft(
    project_dir: Path,
    candidate_path: Path,
) -> PrintedScoreReviewRecord:
    project_root = Path(project_dir).expanduser().resolve()
    candidates, path, candidate_sha256 = load_candidate_set(project_root, candidate_path)
    return PrintedScoreReviewRecord(
        candidate_file_relative_path=path.relative_to(project_root).as_posix(),
        candidate_sha256=candidate_sha256,
        bundle_id=candidates.bundle_id,
        printed_page=candidates.printed_page,
        derivative_sha256=candidates.derivative_sha256,
        model=candidates.model,
        tuning_midi=list(candidates.tuning_midi),
        time_signature_numerator=candidates.time_signature_numerator,
        time_signature_denominator=candidates.time_signature_denominator,
        candidate_warnings=list(candidates.warnings),
        measures=[
            ReviewedScoreMeasure(
                measure_index=measure.measure_index,
                system_index=measure.system_index,
                region=measure.region,
                status="pending",
                events=[
                    _draft_event(index, event)
                    for index, event in enumerate(measure.response.events)
                ],
            )
            for measure in candidates.measures
        ],
    )


def default_review_path(project_dir: Path, record: PrintedScoreReviewRecord) -> Path:
    project_root = Path(project_dir).expanduser().resolve()
    return (
        project_root
        / PRIVATE_REVIEW_RELATIVE_PATH
        / f"page-{record.printed_page:03d}-{record.candidate_sha256[:12]}-review.json"
    )


def save_review_record(
    project_dir: Path,
    record: PrintedScoreReviewRecord,
    *,
    output: Path | None = None,
) -> Path:
    destination = (
        default_review_path(project_dir, record)
        if output is None
        else _project_path(project_dir, output)
    )
    return _atomic_write_text(destination, record.model_dump_json(indent=2) + "\n")


def _verify_record_source(
    project_dir: Path,
    record: PrintedScoreReviewRecord,
) -> tuple[PrintedScoreRecognitionCandidateSet, Path]:
    candidates, candidate_path, current_sha256 = load_candidate_set(
        project_dir,
        Path(record.candidate_file_relative_path),
    )
    if current_sha256 != record.candidate_sha256:
        raise PrintedScoreReviewError(
            "recognition candidates changed after review began; discard the stale review and review again"
        )
    if candidates.derivative_sha256 != record.derivative_sha256:
        raise PrintedScoreReviewError("review derivative identity no longer matches recognition candidates")
    if candidates.bundle_id != record.bundle_id or candidates.printed_page != record.printed_page:
        raise PrintedScoreReviewError("review source identity no longer matches recognition candidates")
    return candidates, candidate_path


def _validate_reviewed_event(
    event: ReviewedScoreEvent,
    *,
    tuning_midi: list[int],
    numerator: int,
) -> None:
    end = event.beat - 1.0 + event.duration_beats
    if end > numerator + 1e-6:
        raise PrintedScoreReviewError(
            f"reviewed event extends past measure: beat={event.beat:g}, duration={event.duration_beats:g}"
        )
    if event.kind == "note":
        assert event.string is not None
        if event.string >= len(tuning_midi):
            raise PrintedScoreReviewError(
                f"reviewed note uses string {event.string} outside {len(tuning_midi)}-string tuning"
            )


def _rest_note_overlap(events: list[ReviewedScoreEvent]) -> bool:
    notes = [event for event in events if event.kind == "note"]
    rests = [event for event in events if event.kind == "rest"]
    for rest in rests:
        rest_start = rest.beat - 1.0
        rest_end = rest_start + rest.duration_beats
        for note in notes:
            note_start = note.beat - 1.0
            note_end = note_start + note.duration_beats
            if max(rest_start, note_start) < min(rest_end, note_end) - 1e-9:
                return True
    return False


def materialize_reviewed_fixture(
    project_dir: Path,
    record: PrintedScoreReviewRecord,
    *,
    bpm: float,
) -> PrintedNotationFixture:
    """Create user-confirmed canonical notation only after every selected measure is reviewed."""

    if bpm <= 0:
        raise ValueError("bpm must be > 0")
    _verify_record_source(project_dir, record)
    if not record.all_measures_reviewed:
        pending = [
            measure.measure_index + 1
            for measure in record.measures
            if measure.status == "pending"
        ]
        raise PrintedScoreReviewError(
            f"cannot materialize reviewed fixture; pending measure review: {pending}"
        )

    note_events: list[PrintedNotationEvent] = []
    rest_events: list[PrintedNotationRestEvent] = []
    for measure in record.measures:
        if _rest_note_overlap(measure.events):
            raise PrintedScoreReviewError(
                f"measure {measure.measure_index + 1} contains an explicit rest overlapping a note"
            )
        canonical_measure = measure.measure_index + 1
        for event in measure.events:
            _validate_reviewed_event(
                event,
                tuning_midi=record.tuning_midi,
                numerator=record.time_signature_numerator,
            )
            confidence = {"human_review": 1.0, "rhythm": 1.0}
            if event.original_vision_confidence is not None:
                confidence["vision_original"] = event.original_vision_confidence
            if event.kind == "note":
                assert event.string is not None and event.fret is not None
                confidence["fret"] = 1.0
                note_events.append(
                    PrintedNotationEvent(
                        measure=canonical_measure,
                        beat=event.beat,
                        duration_beats=event.duration_beats,
                        string=event.string,
                        fret=event.fret,
                        techniques=list(event.techniques),
                        field_confidence=confidence,
                        review_required=False,
                        region=measure.region,
                        human_reviewed=True,
                    )
                )
            else:
                confidence["rest"] = 1.0
                rest_events.append(
                    PrintedNotationRestEvent(
                        measure=canonical_measure,
                        beat=event.beat,
                        duration_beats=event.duration_beats,
                        field_confidence=confidence,
                        review_required=False,
                        region=measure.region,
                        human_reviewed=True,
                    )
                )

    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=list(record.tuning_midi),
        bpm=bpm,
        time_signature=PrintedNotationTimeSignature(
            numerator=record.time_signature_numerator,
            denominator=record.time_signature_denominator,
        ),
        pages=[
            PrintedNotationPage(
                page_number=record.printed_page,
                events=note_events,
                rests=rest_events,
            )
        ],
    )


def default_reviewed_fixture_path(
    project_dir: Path,
    record: PrintedScoreReviewRecord,
) -> Path:
    project_root = Path(project_dir).expanduser().resolve()
    return (
        project_root
        / PRIVATE_RECOGNITION_RELATIVE_PATH
        / f"page-{record.printed_page:03d}-{record.candidate_sha256[:12]}-reviewed-fixture.json"
    )


def write_reviewed_fixture(
    project_dir: Path,
    record: PrintedScoreReviewRecord,
    *,
    bpm: float,
    output: Path | None = None,
) -> Path:
    fixture = materialize_reviewed_fixture(project_dir, record, bpm=bpm)
    destination = (
        default_reviewed_fixture_path(project_dir, record)
        if output is None
        else _project_path(project_dir, output)
    )
    return _atomic_write_text(destination, fixture.model_dump_json(indent=2) + "\n")
