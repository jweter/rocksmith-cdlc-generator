from rocksmith_cdlc_generator.song_preview_loop import PreviewLoopRange
from rocksmith_cdlc_generator.song_preview_transport import build_preview_transport_state


def _loop() -> PreviewLoopRange:
    return PreviewLoopRange(
        start_seconds=10.0,
        end_seconds=14.0,
        duration_seconds=4.0,
        beat_indices=[20, 21],
        beat_times_seconds=[10.0, 12.0],
    )


def test_transport_keeps_position_when_loop_is_disabled() -> None:
    state = build_preview_transport_state(15.25, loop_range=_loop(), loop_enabled=False)

    assert state.requested_position_seconds == 15.25
    assert state.effective_position_seconds == 15.25
    assert state.loop_enabled is False


def test_transport_wraps_position_when_loop_is_enabled() -> None:
    state = build_preview_transport_state(15.25, loop_range=_loop(), loop_enabled=True)

    assert state.requested_position_seconds == 15.25
    assert state.effective_position_seconds == 11.25
    assert state.loop_enabled is True


def test_transport_preserves_preroll_before_loop_start() -> None:
    state = build_preview_transport_state(9.5, loop_range=_loop(), loop_enabled=True)

    assert state.effective_position_seconds == 9.5


def test_transport_rejects_enabled_loop_without_range() -> None:
    try:
        build_preview_transport_state(2.0, loop_enabled=True)
    except ValueError as exc:
        assert str(exc) == "Loop playback requires an explicit loop range"
    else:
        raise AssertionError("Expected missing loop range to be rejected")


def test_transport_deep_copies_loop_range() -> None:
    loop_range = _loop()
    state = build_preview_transport_state(11.0, loop_range=loop_range, loop_enabled=True)

    state.loop_range.beat_indices.append(99)  # type: ignore[union-attr]

    assert loop_range.beat_indices == [20, 21]
