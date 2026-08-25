from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from .hashing import sha256_file
from .models import ProjectManifest
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_source import ArrangementRole, ProjectScoreSource, ScoreArrangementMapping
from .source_import import ImportedSource
from .source_timing_qualification import qualify_project_score_timing


class SharedTimeline(BaseModel):
    """Reviewed score-to-recording transform shared by all confirmed arrangements."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    method: str = "beat-grid-piecewise-linear-v1"
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_role: ArrangementRole
    authority_track_index: int = Field(ge=0)
    authority_output_json: str
    authority_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inherited_roles: list[ArrangementRole]
    audio_beat_start_index: int = Field(ge=0)
    global_offset_seconds: float
    anchor_stride_beats: int = Field(gt=0)
    matched_beats: int = Field(gt=1)
    rms_residual_seconds: float = Field(ge=0)
    median_abs_residual_seconds: float = Field(ge=0)
    max_abs_residual_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    anchors: list[AlignmentAnchor]
    regions: list[AlignmentRegion]
    warnings: list[str] = Field(default_factory=list)
    human_confirmed: Literal[True] = True

    @model_validator(mode="after")
    def roles_are_unique(self) -> "SharedTimeline":
        if len(set(self.inherited_roles)) != len(self.inherited_roles):
            raise ValueError("shared timeline inherited roles must be unique")
        if self.authority_role not in self.inherited_roles:
            raise ValueError("shared timeline authority role must inherit the timeline")
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "SharedTimeline":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def _safe_project_file(project: Path, relative: str) -> Path:
    candidate = (project / relative).resolve()
    if not candidate.is_relative_to(project):
        raise ValueError("shared-score output escaped the project directory")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _current_fanout(project: Path, score: ProjectScoreSource) -> ScoreFanoutManifest:
    path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not path.is_file():
        raise FileNotFoundError("current shared-score fan-out manifest not found")
    manifest = ScoreFanoutManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.score_source_sha256 != score.source_sha256:
        raise ValueError("fan-out manifest does not match the registered score")
    if manifest.score_source_format != score.source_format:
        raise ValueError("fan-out manifest format does not match the registered score")
    confirmed = {
        (mapping.role, mapping.source_track_index)
        for mapping in score.arrangement_mappings
        if mapping.human_confirmed
    }
    actual = {(entry.role, entry.source_track_index) for entry in manifest.arrangements}
    if actual != confirmed:
        raise ValueError("fan-out manifest does not match current human-confirmed score mappings")
    for entry in manifest.arrangements:
        output = _safe_project_file(project, entry.output_json)
        imported = ImportedSource.read_json(output)
        if imported.provenance.source_sha256 != score.source_sha256 or len(imported.tracks) != 1:
            raise ValueError("fan-out output provenance does not match registered score")
        track = imported.tracks[0]
        if track.source_track_index != entry.source_track_index or track.instrument != entry.role.value:
            raise ValueError("fan-out output does not match its confirmed arrangement mapping")
    return manifest


def _authority_mapping(
    score: ProjectScoreSource,
    fanout: ScoreFanoutManifest,
) -> tuple[ScoreArrangementMapping, object]:
    """Choose one explicit confirmed arrangement as timing authority.

    Bass remains preferred for backward compatibility because the existing audio-derived
    Bass reconciliation can independently qualify timing. A project with no Bass may use
    Lead, then Rhythm, instead of fabricating a Bass mapping solely to satisfy the timing
    architecture.
    """

    for role in (ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm):
        mapping = score.mapping_for(role)
        if mapping is None or not mapping.human_confirmed:
            continue
        entry = next(
            (
                item
                for item in fanout.arrangements
                if item.role is role and item.source_track_index == mapping.source_track_index
            ),
            None,
        )
        if entry is not None:
            return mapping, entry
    raise ValueError("at least one human-confirmed score mapping is required to promote shared timing")


def build_shared_timeline_candidate(project_dir: Path) -> SharedTimeline:
    """Build the exact shared-timing candidate that promotion would persist, without writing it.

    Timing authority comes from one explicitly confirmed score role. Bass is preferred
    when present; Lead or Rhythm is valid for partial-arrangement projects. The same
    provenance/currentness checks apply regardless of which role supplies the transform.
    """

    project = project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    score = load_score_for_mapping_review(project)
    fanout = _current_fanout(project, score)
    authority_mapping, authority_entry = _authority_mapping(score, fanout)
    authority_output = _safe_project_file(project, authority_entry.output_json)

    alignment_path = project / "analysis" / "alignment.json"
    if not alignment_path.is_file():
        raise FileNotFoundError(
            f"analysis/alignment.json not found; align the confirmed {authority_mapping.role.value} score output first"
        )
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    if Path(alignment.source_path).expanduser().resolve() != authority_output:
        raise ValueError(
            f"current alignment is not against the authoritative shared-score {authority_mapping.role.value} output"
        )
    if alignment.source_sha256 != score.source_sha256:
        raise ValueError("current alignment score provenance does not match the registered score")
    if alignment.recording_sha256 != manifest.source_sha256:
        raise ValueError("current alignment recording provenance does not match the project recording")
    if alignment.track_index != authority_mapping.source_track_index:
        raise ValueError("current alignment track does not match the confirmed authority mapping")

    roles = sorted(
        (mapping.role for mapping in score.arrangement_mappings if mapping.human_confirmed),
        key=lambda role: role.value,
    )
    return SharedTimeline(
        method=alignment.method,
        recording_sha256=manifest.source_sha256,
        score_sha256=score.source_sha256,
        authority_role=authority_mapping.role,
        authority_track_index=authority_mapping.source_track_index,
        authority_output_json=authority_entry.output_json,
        authority_output_sha256=sha256_file(authority_output),
        inherited_roles=roles,
        audio_beat_start_index=alignment.audio_beat_start_index,
        global_offset_seconds=alignment.global_offset_seconds,
        anchor_stride_beats=alignment.anchor_stride_beats,
        matched_beats=alignment.matched_beats,
        rms_residual_seconds=alignment.rms_residual_seconds,
        median_abs_residual_seconds=alignment.median_abs_residual_seconds,
        max_abs_residual_seconds=alignment.max_abs_residual_seconds,
        confidence=alignment.confidence,
        anchors=alignment.anchors,
        regions=alignment.regions,
        warnings=alignment.warnings,
        human_confirmed=True,
    )


def _promote_shared_timeline_locked(
    project: Path,
    *,
    expected_candidate: SharedTimeline | None = None,
) -> Path:
    timeline = build_shared_timeline_candidate(project)
    if expected_candidate is not None and timeline != expected_candidate:
        raise ValueError(
            "shared timing candidate changed after review; refresh Song Workspace and review the updated alignment before promotion"
        )

    # The existing independent qualification signal is Bass-specific. Keep using it when
    # Bass is the authority, but do not compare Lead/Rhythm symbolic events against a Bass
    # transcription in partial-arrangement projects. Those projects remain behind the same
    # explicit human timing-review boundary.
    if timeline.authority_role is ArrangementRole.bass:
        qualification = qualify_project_score_timing(project, timeline)
        if qualification.status == "review_required":
            raise ValueError(
                "Source timing qualification found a probable score/recording mismatch and blocked timing promotion. "
                f"Repeated evidence prefers {qualification.best_shift_seconds:+.3f}s relative to the current candidate "
                f"({qualification.best_match_count} matches vs {qualification.baseline_match_count} at current timing). "
                "Verify the score/version or correct the alignment before promotion. No automatic timing correction was applied."
            )

    return timeline.write_json(project / "analysis" / "shared_timeline.json")


def promote_shared_timeline(
    project_dir: Path,
    *,
    expected_candidate: SharedTimeline | None = None,
) -> Path:
    """Promote the current reviewed score alignment into song-level timing authority.

    The explicit command invocation is the human acceptance boundary. Promotion never
    chooses a score track automatically: the authority must already be an explicitly
    human-confirmed arrangement. Bass is preferred when configured; otherwise a confirmed
    Lead or Rhythm track may provide timing for a partial-arrangement project.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        return _promote_shared_timeline_locked(project, expected_candidate=expected_candidate)


def load_current_shared_timeline(project_dir: Path) -> SharedTimeline:
    project = project_dir.expanduser().resolve()
    path = project / "analysis" / "shared_timeline.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        timeline = SharedTimeline.read_json(path)
        manifest = ProjectManifest.load(project)
        score = load_score_for_mapping_review(project)
        fanout = _current_fanout(project, score)
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"shared timeline is not current: {exc}") from exc

    if timeline.recording_sha256 != manifest.source_sha256:
        raise ValueError("shared timeline recording does not match current project audio")
    if timeline.score_sha256 != score.source_sha256:
        raise ValueError("shared timeline score does not match current registered score")
    confirmed_roles = sorted(
        (mapping.role for mapping in score.arrangement_mappings if mapping.human_confirmed),
        key=lambda role: role.value,
    )
    if timeline.inherited_roles != confirmed_roles:
        raise ValueError("shared timeline inherited roles do not match current confirmed mappings")
    authority = score.mapping_for(timeline.authority_role)
    if authority is None or not authority.human_confirmed or authority.source_track_index != timeline.authority_track_index:
        raise ValueError("shared timeline authority mapping is no longer current")
    entry = next((item for item in fanout.arrangements if item.role is timeline.authority_role), None)
    if entry is None or entry.output_json != timeline.authority_output_json:
        raise ValueError("shared timeline authority output is no longer current")
    authority_output = _safe_project_file(project, timeline.authority_output_json)
    if sha256_file(authority_output) != timeline.authority_output_sha256:
        raise ValueError("shared timeline authority output content has changed")
    return timeline


def alignment_for_role(project_dir: Path, role: ArrangementRole) -> AlignmentReport:
    """Materialize one arrangement view of the shared song-level timing transform."""

    project = project_dir.expanduser().resolve()
    timeline = load_current_shared_timeline(project)
    if role not in timeline.inherited_roles:
        raise ValueError(f"{role.value} does not inherit the current shared timeline")
    score = load_score_for_mapping_review(project)
    fanout = _current_fanout(project, score)
    mapping = score.mapping_for(role)
    if mapping is None or not mapping.human_confirmed:
        raise ValueError(f"{role.value} score mapping is not human-confirmed")
    entry = next((item for item in fanout.arrangements if item.role is role), None)
    if entry is None or entry.source_track_index != mapping.source_track_index:
        raise ValueError(f"{role.value} fan-out output is not current")
    output = _safe_project_file(project, entry.output_json)

    return AlignmentReport(
        method=timeline.method,
        source_path=str(output),
        source_sha256=timeline.score_sha256,
        recording_sha256=timeline.recording_sha256,
        track_index=mapping.source_track_index,
        audio_beat_start_index=timeline.audio_beat_start_index,
        global_offset_seconds=timeline.global_offset_seconds,
        anchor_stride_beats=timeline.anchor_stride_beats,
        matched_beats=timeline.matched_beats,
        rms_residual_seconds=timeline.rms_residual_seconds,
        median_abs_residual_seconds=timeline.median_abs_residual_seconds,
        max_abs_residual_seconds=timeline.max_abs_residual_seconds,
        confidence=timeline.confidence,
        anchors=timeline.anchors,
        regions=timeline.regions,
        warnings=timeline.warnings,
    )
