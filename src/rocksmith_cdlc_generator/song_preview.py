from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .musicxml_multi_import import (
    ArrangementKind,
    MusicXMLArrangementImportManifest,
    MusicXMLArrangementManifestEntry,
)
from .source_import import (
    ImportedSource,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrustClass,
)


class PreviewNoteEvent(BaseModel):
    event_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass
    review_required: bool

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


class PreviewArrangement(BaseModel):
    instrument: ArrangementKind
    part_index: int = Field(ge=0)
    part_id: str
    part_name: str
    source_track_name: str | None = None
    tuning_midi: list[int] | None = None
    output_json: str
    note_count: int = Field(ge=0)
    notes: list[PreviewNoteEvent]
    warnings: list[str] = Field(default_factory=list)


class SongPreviewSnapshot(BaseModel):
    """Read-only, GUI-friendly projection of one trusted arrangement manifest."""

    schema_version: int = 1
    source_filename: str
    source_sha256: str
    beat_times_seconds: list[float] = Field(default_factory=list)
    tempo_events: list[SourceTempoEvent] = Field(default_factory=list)
    time_signatures: list[SourceTimeSignatureEvent] = Field(default_factory=list)
    arrangements: list[PreviewArrangement]


class PreviewTimelineLane(BaseModel):
    """One arrangement lane clipped to a requested preview time window."""

    instrument: ArrangementKind
    part_name: str
    tuning_midi: list[int] | None = None
    notes: list[PreviewNoteEvent] = Field(default_factory=list)
    review_required_count: int = Field(ge=0)


class PreviewTimelineWindow(BaseModel):
    """Read-only timeline projection suitable for a GUI viewport."""

    schema_version: int = 1
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    beat_times_seconds: list[float] = Field(default_factory=list)
    lanes: list[PreviewTimelineLane] = Field(default_factory=list)


class PreviewReviewItem(BaseModel):
    """Stable pointer to one arrangement event that still needs human review."""

    review_id: str
    instrument: ArrangementKind
    part_name: str
    event_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass


class PreviewReviewQueue(BaseModel):
    """Deterministic read-only queue for GUI next/previous-review navigation."""

    schema_version: int = 1
    items: list[PreviewReviewItem] = Field(default_factory=list)


_ARRANGEMENT_ORDER: dict[ArrangementKind, int] = {
    "lead": 0,
    "rhythm": 1,
    "bass": 2,
}


def _resolve_project_file(project_dir: Path, candidate: Path, *, label: str) -> Path:
    project_dir = project_dir.resolve()
    path = candidate if candidate.is_absolute() else project_dir / candidate
    path = path.resolve()
    try:
        path.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError(f"{label} escaped project directory: {path}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def _validate_manifest_entries(entries: list[MusicXMLArrangementManifestEntry]) -> None:
    if not entries:
        raise ValueError("MusicXML arrangement manifest contains no arrangements")
    roles = [entry.instrument for entry in entries]
    if len(set(roles)) != len(roles):
        raise ValueError("MusicXML arrangement manifest contains duplicate arrangement roles")
    parts = [entry.part_index for entry in entries]
    if len(set(parts)) != len(parts):
        raise ValueError("MusicXML arrangement manifest assigns one source part to multiple roles")


def _validate_imported_arrangement(
    imported: ImportedSource,
    entry: MusicXMLArrangementManifestEntry,
    manifest: MusicXMLArrangementImportManifest,
) -> None:
    provenance = imported.provenance
    if provenance.source_filename != manifest.source_filename or provenance.source_sha256 != manifest.source_sha256:
        raise ValueError("Imported arrangement provenance does not match the trusted manifest")
    if len(imported.tracks) != 1:
        raise ValueError("Preview arrangement must contain exactly one normalized source track")
    track = imported.tracks[0]
    if track.source_track_index != entry.part_index or track.instrument != entry.instrument:
        raise ValueError("Imported arrangement track does not match the trusted manifest selection")
    if entry.tuning_midi is not None and track.tuning_midi != entry.tuning_midi:
        raise ValueError("Imported arrangement tuning does not match the trusted manifest")
    if len(track.notes) != entry.pitched_note_count:
        raise ValueError("Imported arrangement note count does not match the trusted manifest")


def _same_timebase(left: ImportedSource, right: ImportedSource) -> bool:
    return (
        left.beat_times_seconds == right.beat_times_seconds
        and left.tempo_events == right.tempo_events
        and left.time_signatures == right.time_signatures
    )


def load_musicxml_preview_snapshot(project_dir: Path, manifest_path: Path) -> SongPreviewSnapshot:
    """Load a trusted MusicXML arrangement manifest into a read-only preview snapshot.

    This function never edits timing, notes, manifests, or imported artifacts. It also
    refuses project-path escapes, mixed provenance, manifest/output selection drift,
    and inconsistent timebases so a GUI cannot silently render a mixed arrangement set.
    """

    project_dir = project_dir.resolve()
    manifest_file = _resolve_project_file(project_dir, manifest_path, label="Arrangement manifest")
    manifest = MusicXMLArrangementImportManifest.model_validate_json(
        manifest_file.read_text(encoding="utf-8")
    )
    _validate_manifest_entries(manifest.arrangements)

    preview_arrangements: list[PreviewArrangement] = []
    canonical: ImportedSource | None = None

    for entry in manifest.arrangements:
        output_file = _resolve_project_file(
            project_dir,
            Path(entry.output_json),
            label=f"{entry.instrument.title()} arrangement JSON",
        )
        imported = ImportedSource.read_json(output_file)
        _validate_imported_arrangement(imported, entry, manifest)

        if canonical is None:
            canonical = imported
        elif not _same_timebase(canonical, imported):
            raise ValueError("Imported arrangements do not share one canonical preview timebase")

        track = imported.tracks[0]
        notes = [
            PreviewNoteEvent(
                event_index=index,
                start_seconds=note.start_seconds,
                duration_seconds=note.duration_seconds,
                midi=note.midi,
                note_name=note.note_name,
                string_index=note.string_index,
                fret=note.fret,
                techniques=list(note.techniques),
                import_confidence=note.import_confidence,
                trust_class=note.trust_class,
                review_required=note.review_required,
            )
            for index, note in enumerate(track.notes)
        ]
        preview_arrangements.append(
            PreviewArrangement(
                instrument=entry.instrument,
                part_index=entry.part_index,
                part_id=entry.part_id,
                part_name=entry.part_name,
                source_track_name=track.name,
                tuning_midi=track.tuning_midi,
                output_json=entry.output_json,
                note_count=len(notes),
                notes=notes,
                warnings=list(imported.warnings),
            )
        )

    assert canonical is not None  # guarded by _validate_manifest_entries
    return SongPreviewSnapshot(
        source_filename=manifest.source_filename,
        source_sha256=manifest.source_sha256,
        beat_times_seconds=list(canonical.beat_times_seconds),
        tempo_events=list(canonical.tempo_events),
        time_signatures=list(canonical.time_signatures),
        arrangements=preview_arrangements,
    )


def build_preview_timeline_window(
    snapshot: SongPreviewSnapshot,
    start_seconds: float,
    end_seconds: float,
) -> PreviewTimelineWindow:
    """Project a snapshot into immutable timeline lanes without changing source timing.

    Notes are included when any part of their duration intersects the requested window.
    Event indices remain those of the full arrangement, allowing a future GUI to select
    an event without treating the viewport projection as a new authoritative chart.
    """

    if start_seconds < 0:
        raise ValueError("Preview window start must be non-negative")
    if end_seconds < start_seconds:
        raise ValueError("Preview window end must be greater than or equal to start")

    beats = [
        beat
        for beat in snapshot.beat_times_seconds
        if start_seconds <= beat <= end_seconds
    ]
    lanes: list[PreviewTimelineLane] = []
    for arrangement in snapshot.arrangements:
        notes = [
            note.model_copy(deep=True)
            for note in arrangement.notes
            if note.start_seconds <= end_seconds and note.end_seconds >= start_seconds
        ]
        lanes.append(
            PreviewTimelineLane(
                instrument=arrangement.instrument,
                part_name=arrangement.part_name,
                tuning_midi=(
                    list(arrangement.tuning_midi)
                    if arrangement.tuning_midi is not None
                    else None
                ),
                notes=notes,
                review_required_count=sum(note.review_required for note in notes),
            )
        )

    return PreviewTimelineWindow(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        beat_times_seconds=beats,
        lanes=lanes,
    )


def build_preview_review_queue(snapshot: SongPreviewSnapshot) -> PreviewReviewQueue:
    """Return all review-required notes in deterministic cross-arrangement order.

    Chronological position is primary so next/previous navigation follows the song.
    At the same onset, lower-confidence events are surfaced first, then Lead/Rhythm/Bass
    order provides a stable tie-breaker. The queue carries copied values only and never
    mutates the trusted preview snapshot or its source artifacts.
    """

    items: list[PreviewReviewItem] = []
    for arrangement in snapshot.arrangements:
        for note in arrangement.notes:
            if not note.review_required:
                continue
            items.append(
                PreviewReviewItem(
                    review_id=f"{arrangement.instrument}:{note.event_index}",
                    instrument=arrangement.instrument,
                    part_name=arrangement.part_name,
                    event_index=note.event_index,
                    start_seconds=note.start_seconds,
                    duration_seconds=note.duration_seconds,
                    midi=note.midi,
                    note_name=note.note_name,
                    string_index=note.string_index,
                    fret=note.fret,
                    techniques=list(note.techniques),
                    import_confidence=note.import_confidence,
                    trust_class=note.trust_class,
                )
            )

    items.sort(
        key=lambda item: (
            item.start_seconds,
            item.import_confidence,
            _ARRANGEMENT_ORDER[item.instrument],
            item.event_index,
        )
    )
    return PreviewReviewQueue(items=items)
