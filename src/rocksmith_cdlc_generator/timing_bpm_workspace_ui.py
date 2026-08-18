from __future__ import annotations

from collections.abc import Sequence


def local_bpm_for_beat(beat_times: Sequence[float], beat_index: int) -> float | None:
    """Return the local beat-to-beat tempo for one reviewed/detected beat.

    Prefer the interval beginning at the selected beat so the displayed tempo describes
    what the user is about to hear. For the final beat, use the preceding interval.
    Invalid, duplicate, or insufficient beat times fail closed as unavailable.
    """

    if beat_index < 0 or beat_index >= len(beat_times) or len(beat_times) < 2:
        return None
    if beat_index < len(beat_times) - 1:
        start = float(beat_times[beat_index])
        end = float(beat_times[beat_index + 1])
    else:
        start = float(beat_times[beat_index - 1])
        end = float(beat_times[beat_index])
    interval = end - start
    if interval <= 0:
        return None
    return 60.0 / interval


class TimingBpmWorkspaceMixin:
    """Show local tempo beside the existing timing-review beat description."""

    def _refresh_selected_beat_text(self) -> None:
        super()._refresh_selected_beat_text()
        if not hasattr(self, "timing_review_var"):
            return
        snapshot = getattr(self, "snapshot", None)
        if snapshot is None:
            return
        index = self._nearest_beat_index()
        if index is None:
            return
        reviewed = getattr(self, "reviewed_timing", None)
        beat_times = (
            [anchor.reviewed_time_seconds for anchor in reviewed.anchors]
            if reviewed is not None
            else list(snapshot.timeline.beat_times)
        )
        bpm = local_bpm_for_beat(beat_times, index)
        if bpm is None:
            return
        self.timing_review_var.set(self.timing_review_var.get() + f" · local tempo {bpm:.2f} BPM")
