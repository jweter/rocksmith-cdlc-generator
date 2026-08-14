from __future__ import annotations

from pathlib import Path
from typing import Any

from .guitarpro_import import (
    _BASS_PROGRAMS,
    _GUITAR_PROGRAMS,
    _load_guitarpro,
    _track_program,
    _track_score,
)
from .hashing import sha256_file
from .musicxml_import import (
    _load_root,
    _local,
    _part_metadata,
    _part_score,
    _staff_tuning,
)
from .score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)

_SUPPORTED_GUITARPRO = {".gp3", ".gp4", ".gp5"}
_SUPPORTED_MUSICXML = {".xml", ".musicxml", ".mxl"}


def _role_basis(
    *,
    role: ArrangementRole,
    name: str | None,
    programs: list[int],
    tuning: list[int] | None,
) -> list[str]:
    lowered = (name or "").lower()
    basis: list[str] = []
    if role is ArrangementRole.bass:
        if "bass" in lowered:
            basis.append("track name contains bass")
        if any(program in _BASS_PROGRAMS for program in programs):
            basis.append("MIDI program is bass-family")
        if tuning and len(tuning) in {4, 5, 6} and min(tuning) < 36:
            basis.append("low-register bass-like tuning")
        return basis

    if any(program in _GUITAR_PROGRAMS for program in programs):
        basis.append("MIDI program is guitar-family")
    if tuning and len(tuning) == 6:
        basis.append("six-string guitar tuning")
    elif tuning and 5 <= len(tuning) <= 7:
        basis.append("guitar-like string count")
    if "guitar" in lowered:
        basis.append("track name contains guitar")

    if role is ArrangementRole.lead:
        if "lead" in lowered:
            basis.append("track name contains lead")
        if "solo" in lowered:
            basis.append("track name contains solo")
        if "melody" in lowered:
            basis.append("track name contains melody")
    else:
        if "rhythm" in lowered or "rythm" in lowered:
            basis.append("track name contains rhythm")
        if "chord" in lowered:
            basis.append("track name contains chord")
        if "acoustic" in lowered:
            basis.append("track name contains acoustic")
    return basis


def _proposal_confidence(
    role: ArrangementRole,
    *,
    best_score: int,
    second_score: int | None,
    basis: list[str],
) -> float:
    explicit = {
        ArrangementRole.bass: "track name contains bass",
        ArrangementRole.lead: "track name contains lead",
        ArrangementRole.rhythm: "track name contains rhythm",
    }[role]
    if explicit in basis and best_score > 0 and (second_score is None or best_score > second_score):
        return 1.0
    if best_score >= 80:
        return 0.95
    if best_score >= 50:
        return 0.85
    return 0.7


def _propose_mappings(
    tracks: list[ScoreTrackCandidate],
    scores_by_role: dict[ArrangementRole, list[int]],
    programs_by_index: dict[int, list[int]],
) -> list[ScoreArrangementMapping]:
    mappings: list[ScoreArrangementMapping] = []
    for role in ArrangementRole:
        scores = scores_by_role[role]
        credible = [(score, index) for index, score in enumerate(scores) if score > 0]
        if not credible:
            continue
        credible.sort(reverse=True)
        best_score = credible[0][0]
        winners = [index for score, index in credible if score == best_score]
        if len(winners) != 1:
            # Preserve ambiguity in the inventory. A tied role is deliberately not
            # converted into a mapping because a mapping would look like a choice.
            continue
        index = winners[0]
        candidate = tracks[index]
        basis = _role_basis(
            role=role,
            name=candidate.name,
            programs=programs_by_index.get(candidate.source_track_index, []),
            tuning=candidate.tuning_midi,
        )
        second_score = next((score for score, other in credible if other != index), None)
        mappings.append(
            ScoreArrangementMapping(
                role=role,
                source_track_index=candidate.source_track_index,
                confidence=_proposal_confidence(
                    role,
                    best_score=best_score,
                    second_score=second_score,
                    basis=basis,
                ),
                basis=basis,
                human_confirmed=False,
            )
        )
    return mappings


def _musicxml_note_count(part: Any) -> int:
    count = 0
    for node in part.iter():
        if _local(node.tag) != "note":
            continue
        if any(_local(child.tag) == "rest" for child in node):
            continue
        if any(_local(child.tag) == "pitch" for child in node):
            count += 1
    return count


def _musicxml_tuning(part: Any) -> list[int] | None:
    tuning = _staff_tuning(part)
    if tuning is None:
        return None
    # MusicXML staff-tuning line 1 describes the highest physical string, while
    # the shared project contract uses Rocksmith-style low-string-first order.
    return list(reversed(tuning))


def inventory_musicxml(
    path: Path,
    *,
    imported_relative_path: str | None = None,
) -> ProjectScoreSource:
    path = path.resolve()
    if path.suffix.lower() not in _SUPPORTED_MUSICXML:
        raise ValueError("MusicXML inventory supports .xml, .musicxml, and .mxl")
    if not path.is_file():
        raise FileNotFoundError(path)

    root = _load_root(path)
    parts = [node for node in root if _local(node.tag) == "part"]
    if not parts:
        raise ValueError("MusicXML contains no parts")
    metadata = _part_metadata(root)

    tracks: list[ScoreTrackCandidate] = []
    programs_by_index: dict[int, list[int]] = {}
    scores_by_role = {role: [] for role in ArrangementRole}
    for index, part in enumerate(parts):
        meta = metadata.get(part.attrib.get("id", ""), {})
        name = str(meta.get("name") or "") or None
        programs = [int(value) for value in meta.get("programs", [])]
        tuning = _musicxml_tuning(part)
        hint = _instrument_hint(name=name, programs=programs, tuning=tuning)
        tracks.append(
            ScoreTrackCandidate(
                source_track_index=index,
                name=name,
                instrument_hint=hint,
                tuning_midi=tuning,
                note_count=_musicxml_note_count(part),
            )
        )
        programs_by_index[index] = programs
        for role in ArrangementRole:
            scores_by_role[role].append(_part_score(part, meta, role.value))

    source_format = "mxl" if path.suffix.lower() == ".mxl" else "musicxml"
    return ProjectScoreSource(
        source_filename=path.name,
        source_sha256=sha256_file(path),
        source_format=source_format,
        imported_relative_path=imported_relative_path or path.name,
        tracks=tracks,
        arrangement_mappings=_propose_mappings(tracks, scores_by_role, programs_by_index),
    )


def _guitarpro_note_count(track: Any) -> int:
    return sum(
        len(getattr(beat, "notes", []) or [])
        for measure in getattr(track, "measures", []) or []
        for voice in getattr(measure, "voices", []) or []
        for beat in getattr(voice, "beats", []) or []
    )


def _guitarpro_tuning(track: Any) -> list[int] | None:
    strings = list(getattr(track, "strings", []) or [])
    if not strings:
        return None
    rows = [(int(getattr(string, "number")), int(getattr(string, "value"))) for string in strings]
    rows.sort(key=lambda item: item[0], reverse=True)
    return [midi for _, midi in rows]


def inventory_guitarpro_song(
    song: Any,
    *,
    source_path: Path,
    source_sha256: str,
    imported_relative_path: str | None = None,
) -> ProjectScoreSource:
    raw_tracks = list(getattr(song, "tracks", []) or [])
    if not raw_tracks:
        raise ValueError("Guitar Pro file contains no tracks")

    tracks: list[ScoreTrackCandidate] = []
    programs_by_index: dict[int, list[int]] = {}
    scores_by_role = {role: [] for role in ArrangementRole}
    for index, track in enumerate(raw_tracks):
        name = getattr(track, "name", None)
        program = _track_program(track)
        programs = [program] if program is not None else []
        tuning = _guitarpro_tuning(track)
        tracks.append(
            ScoreTrackCandidate(
                source_track_index=index,
                name=name,
                instrument_hint=_instrument_hint(name=name, programs=programs, tuning=tuning),
                tuning_midi=tuning,
                note_count=_guitarpro_note_count(track),
            )
        )
        programs_by_index[index] = programs
        for role in ArrangementRole:
            scores_by_role[role].append(_track_score(track, role.value))

    return ProjectScoreSource(
        source_filename=source_path.name,
        source_sha256=source_sha256,
        source_format=source_path.suffix.lower().lstrip("."),
        imported_relative_path=imported_relative_path or source_path.name,
        tracks=tracks,
        arrangement_mappings=_propose_mappings(tracks, scores_by_role, programs_by_index),
    )


def inventory_guitarpro(
    path: Path,
    *,
    imported_relative_path: str | None = None,
) -> ProjectScoreSource:
    path = path.resolve()
    if path.suffix.lower() not in _SUPPORTED_GUITARPRO:
        raise ValueError("Guitar Pro inventory supports .gp3, .gp4, and .gp5")
    if not path.is_file():
        raise FileNotFoundError(path)
    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(path))
    except Exception as exc:
        raise ValueError(f"Failed to parse Guitar Pro file: {path.name}") from exc
    return inventory_guitarpro_song(
        song,
        source_path=path,
        source_sha256=sha256_file(path),
        imported_relative_path=imported_relative_path,
    )


def inventory_score(
    path: Path,
    *,
    imported_relative_path: str | None = None,
) -> ProjectScoreSource:
    suffix = path.suffix.lower()
    if suffix in _SUPPORTED_MUSICXML:
        return inventory_musicxml(path, imported_relative_path=imported_relative_path)
    if suffix in _SUPPORTED_GUITARPRO:
        return inventory_guitarpro(path, imported_relative_path=imported_relative_path)
    raise ValueError("Shared score inventory supports MusicXML/MXL and Guitar Pro 3-5")


def _instrument_hint(
    *,
    name: str | None,
    programs: list[int],
    tuning: list[int] | None,
) -> str | None:
    lowered = (name or "").lower()
    if "bass" in lowered or any(program in _BASS_PROGRAMS for program in programs):
        return "bass"
    if "guitar" in lowered or any(program in _GUITAR_PROGRAMS for program in programs):
        return "guitar"
    if tuning and len(tuning) in {4, 5, 6} and min(tuning) < 36:
        return "bass"
    if tuning and 5 <= len(tuning) <= 7:
        return "guitar"
    return None
