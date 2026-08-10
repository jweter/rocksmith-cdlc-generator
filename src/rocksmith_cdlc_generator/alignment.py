from __future__ import annotations

from bisect import bisect_right
from math import sqrt
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field, model_validator

from .beats import TempoMap, read_tempo_map
from .source_import import ImportedSource


class AlignmentAnchor(BaseModel):
    source_time_seconds: float = Field(ge=0)
    audio_time_seconds: float = Field(ge=0)
    source_beat_index: int = Field(ge=0)
    audio_beat_index: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class AlignmentRegion(BaseModel):
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(ge=0)
    audio_start_seconds: float = Field(ge=0)
    audio_end_seconds: float = Field(ge=0)
    rms_residual_seconds: float = Field(ge=0)
    max_abs_residual_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class AlignmentReport(BaseModel):
    schema_version: int = 1
    method: str = "beat-grid-piecewise-linear-v1"
    source_path: str
    source_sha256: str
    track_index: int = Field(ge=0)
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

    @model_validator(mode="after")
    def anchors_are_monotonic(self) -> "AlignmentReport":
        source = [a.source_time_seconds for a in self.anchors]
        audio = [a.audio_time_seconds for a in self.anchors]
        if any(b <= a for a, b in zip(source, source[1:])):
            raise ValueError("alignment source anchors must be strictly increasing")
        if any(b <= a for a, b in zip(audio, audio[1:])):
            raise ValueError("alignment audio anchors must be strictly increasing")
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def _source_end(source: ImportedSource, track_index: int) -> float:
    track = next((t for t in source.tracks if t.source_track_index == track_index), None)
    if track is None:
        raise ValueError(f"source track index {track_index} not found")
    if not track.notes:
        raise ValueError("selected source track has no notes")
    return max(n.start_seconds + n.duration_seconds for n in track.notes)


def _source_beats(source: ImportedSource, track_index: int) -> list[float]:
    end = _source_end(source, track_index)
    tempos = sorted(source.tempo_events, key=lambda e: e.time_seconds)
    if not tempos:
        raise ValueError("imported source has no tempo events; alignment needs a symbolic beat grid")
    if tempos[0].time_seconds > 1e-6:
        raise ValueError("first source tempo event must begin at time 0 for automatic beat alignment")

    beats: list[float] = []
    for index, event in enumerate(tempos):
        segment_end = tempos[index + 1].time_seconds if index + 1 < len(tempos) else end + 1e-9
        step = 60.0 / event.bpm
        time = event.time_seconds
        if beats and abs(time - beats[-1]) < 1e-6:
            time += step
        while time < segment_end - 1e-9 and time <= end + 1e-9:
            if not beats or time > beats[-1] + 1e-6:
                beats.append(time)
            time += step
    if len(beats) < 2:
        raise ValueError("symbolic source does not contain enough beat span to align")
    return beats


def _window_score(source_beats: list[float], audio_times: list[float], start: int) -> float:
    pairs = min(16, len(source_beats) - 1, len(audio_times) - start - 1)
    if pairs < 4:
        return float("inf")
    errors: list[float] = []
    for i in range(pairs):
        source_interval = source_beats[i + 1] - source_beats[i]
        audio_interval = audio_times[start + i + 1] - audio_times[start + i]
        errors.append(abs(audio_interval - source_interval) / source_interval)
    return median(errors)


def _choose_audio_start(source_beats: list[float], tempo_map: TempoMap) -> tuple[int, list[str]]:
    audio_times = [beat.time for beat in tempo_map.beats]
    max_start = min(32, max(0, len(audio_times) - 5))
    scores = [(start, _window_score(source_beats, audio_times, start)) for start in range(max_start + 1)]
    scores = [item for item in scores if item[1] != float("inf")]
    if not scores:
        raise ValueError("audio tempo map does not contain enough beats for alignment")
    scores.sort(key=lambda item: (item[1], item[0]))
    best_start, best_score = scores[0]
    warnings: list[str] = []
    if len(scores) > 1 and scores[1][1] - best_score < 0.015:
        warnings.append(
            "Automatic audio start-beat selection is weakly distinguished; review alignment or pass --audio-beat-index."
        )
    if best_score > 0.20:
        warnings.append("Symbolic and audio beat intervals differ substantially; alignment confidence is reduced.")
    return best_start, warnings


def _interpolate(anchors: list[AlignmentAnchor], source_time: float) -> float:
    if source_time <= anchors[0].source_time_seconds:
        first, second = anchors[0], anchors[1]
    elif source_time >= anchors[-1].source_time_seconds:
        first, second = anchors[-2], anchors[-1]
    else:
        xs = [a.source_time_seconds for a in anchors]
        right = bisect_right(xs, source_time)
        first, second = anchors[right - 1], anchors[right]
    span = second.source_time_seconds - first.source_time_seconds
    ratio = (source_time - first.source_time_seconds) / span
    return first.audio_time_seconds + ratio * (second.audio_time_seconds - first.audio_time_seconds)


def map_source_time(report: AlignmentReport, source_time_seconds: float) -> float:
    return _interpolate(report.anchors, source_time_seconds)


def align_source_to_tempo_map(
    source: ImportedSource,
    tempo_map: TempoMap,
    *,
    source_path: Path,
    track_index: int | None = None,
    audio_beat_index: int | None = None,
    anchor_stride_beats: int = 8,
) -> AlignmentReport:
    if anchor_stride_beats < 2:
        raise ValueError("anchor stride must be at least 2 beats")
    if not source.tracks:
        raise ValueError("imported source has no tracks")
    selected_track = source.tracks[0].source_track_index if track_index is None else track_index
    source_beats = _source_beats(source, selected_track)
    if len(tempo_map.beats) < 4:
        raise ValueError("audio tempo map needs at least four beats")

    warnings: list[str] = []
    if audio_beat_index is None:
        audio_start, auto_warnings = _choose_audio_start(source_beats, tempo_map)
        warnings.extend(auto_warnings)
    else:
        audio_start = audio_beat_index
        if audio_start < 0 or audio_start >= len(tempo_map.beats) - 1:
            raise ValueError("audio beat index is outside the tempo map")

    matched = min(len(source_beats), len(tempo_map.beats) - audio_start)
    if matched < 4:
        raise ValueError("fewer than four beats overlap between symbolic source and audio")
    source_beats = source_beats[:matched]
    audio_beats = tempo_map.beats[audio_start : audio_start + matched]

    anchor_indices = list(range(0, matched, anchor_stride_beats))
    if anchor_indices[-1] != matched - 1:
        anchor_indices.append(matched - 1)
    anchors = [
        AlignmentAnchor(
            source_time_seconds=source_beats[i],
            audio_time_seconds=audio_beats[i].time,
            source_beat_index=i,
            audio_beat_index=audio_start + i,
            confidence=audio_beats[i].confidence,
        )
        for i in anchor_indices
    ]

    residuals = [audio_beats[i].time - _interpolate(anchors, source_beats[i]) for i in range(matched)]
    abs_residuals = [abs(value) for value in residuals]
    rms = sqrt(sum(value * value for value in residuals) / len(residuals))
    med = median(abs_residuals)
    maximum = max(abs_residuals)
    mean_beat_conf = sum(beat.confidence for beat in audio_beats) / matched
    residual_factor = max(0.0, 1.0 - med / 0.12)
    confidence = max(0.0, min(1.0, mean_beat_conf * residual_factor))

    regions: list[AlignmentRegion] = []
    for left, right in zip(anchor_indices, anchor_indices[1:]):
        region_residuals = residuals[left : right + 1]
        region_abs = [abs(value) for value in region_residuals]
        region_rms = sqrt(sum(value * value for value in region_residuals) / len(region_residuals))
        region_mean_conf = sum(beat.confidence for beat in audio_beats[left : right + 1]) / len(region_residuals)
        region_factor = max(0.0, 1.0 - median(region_abs) / 0.12)
        regions.append(
            AlignmentRegion(
                source_start_seconds=source_beats[left],
                source_end_seconds=source_beats[right],
                audio_start_seconds=audio_beats[left].time,
                audio_end_seconds=audio_beats[right].time,
                rms_residual_seconds=region_rms,
                max_abs_residual_seconds=max(region_abs),
                confidence=max(0.0, min(1.0, region_mean_conf * region_factor)),
            )
        )

    if med > 0.08:
        warnings.append("Median beat-grid alignment residual exceeds 80 ms; review before reconciliation.")
    if confidence < 0.60:
        warnings.append("Overall alignment confidence is below 0.60; do not auto-verify symbolic notes.")

    return AlignmentReport(
        source_path=str(source_path.resolve()),
        source_sha256=source.provenance.source_sha256,
        track_index=selected_track,
        audio_beat_start_index=audio_start,
        global_offset_seconds=audio_beats[0].time - source_beats[0],
        anchor_stride_beats=anchor_stride_beats,
        matched_beats=matched,
        rms_residual_seconds=rms,
        median_abs_residual_seconds=med,
        max_abs_residual_seconds=maximum,
        confidence=confidence,
        anchors=anchors,
        regions=regions,
        warnings=warnings,
    )


def align_project_source(
    project_dir: Path,
    source_path: Path,
    *,
    track_index: int | None = None,
    audio_beat_index: int | None = None,
    anchor_stride_beats: int = 8,
) -> Path:
    project_dir = project_dir.resolve()
    source_path = source_path.resolve()
    source = ImportedSource.read_json(source_path)
    tempo_path = project_dir / "analysis" / "tempo_map.json"
    if not tempo_path.is_file():
        raise FileNotFoundError("analysis/tempo_map.json not found; run `cdlc tempo` first")
    report = align_source_to_tempo_map(
        source,
        read_tempo_map(tempo_path),
        source_path=source_path,
        track_index=track_index,
        audio_beat_index=audio_beat_index,
        anchor_stride_beats=anchor_stride_beats,
    )
    return report.write_json(project_dir / "analysis" / "alignment.json")
