from __future__ import annotations

from pathlib import Path

from .source_import import ImportedSource, SourceTrustClass
from .source_track_trust_review import (
    ArrangementRoleName,
    load_current_track_source_trust_review,
)


def apply_current_track_source_trust(
    project_dir: Path,
    source: ImportedSource,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
) -> tuple[ImportedSource, bool]:
    """Project exact current track acceptance into a copied read model.

    The persisted fan-out source remains immutable. A current provenance-bound track
    acceptance upgrades only the copied note trust class to ``user_confirmed``. Existing
    ``review_required`` flags and all timing/position/technique/chord facts remain
    unchanged so independent human-review reasons stay authoritative.
    """

    copied = source.model_copy(deep=True)
    layer = load_current_track_source_trust_review(project_dir)
    if layer is None:
        return copied, False

    acceptance = layer.acceptance_for(arrangement)
    if acceptance is None:
        return copied, False
    if acceptance.source_track_index != source_track_index:
        raise ValueError("Track trust projection source track does not match current acceptance")

    project = project_dir.expanduser().resolve()
    expected_path = (project / acceptance.output_json).resolve()
    if not expected_path.is_relative_to(project) or not expected_path.is_file():
        raise ValueError("Track trust projection source is not a safe current fan-out file")
    expected = ImportedSource.read_json(expected_path)
    if copied.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise ValueError("Track trust projection input does not match accepted fan-out content")
    if len(copied.tracks) != 1:
        raise ValueError("Track trust projection requires exactly one source track")

    track = copied.tracks[0]
    if track.instrument != arrangement or track.source_track_index != source_track_index:
        raise ValueError("Track trust projection input no longer matches arrangement authority")

    for note in track.notes:
        if note.trust_class not in {
            SourceTrustClass.symbolic_unverified,
            SourceTrustClass.symbolic_verified,
        }:
            raise ValueError("Track trust projection encountered non-symbolic source trust")
        note.trust_class = SourceTrustClass.user_confirmed

    return copied, True
