from rocksmith_cdlc_generator.human_review_marks import (
    clear_event_mark,
    load_current_human_review_layer,
    mark_event,
)


def test_human_review_mark_persists_and_replaces_state(tmp_path) -> None:
    layer = mark_event(
        tmp_path,
        source_sha256="abc",
        arrangement="lead",
        event_index=12,
        source_start_seconds=10.5,
        midi=64,
        string_index=2,
        fret=4,
        state="questionable",
    )
    assert len(layer.marks) == 1
    assert layer.marks[0].state == "questionable"

    layer = mark_event(
        tmp_path,
        source_sha256="abc",
        arrangement="lead",
        event_index=12,
        source_start_seconds=10.5,
        midi=64,
        string_index=2,
        fret=4,
        state="wrong",
    )
    assert len(layer.marks) == 1
    assert layer.marks[0].state == "wrong"
    assert load_current_human_review_layer(tmp_path, "abc") is not None
    assert load_current_human_review_layer(tmp_path, "different") is None


def test_clear_mark_removes_only_selected_event(tmp_path) -> None:
    for event_index in (1, 2):
        mark_event(
            tmp_path,
            source_sha256="abc",
            arrangement="rhythm",
            event_index=event_index,
            source_start_seconds=float(event_index),
            midi=60 + event_index,
            string_index=0,
            fret=event_index,
            state="questionable",
        )
    layer = clear_event_mark(tmp_path, source_sha256="abc", arrangement="rhythm", event_index=1)
    assert [mark.event_index for mark in layer.marks] == [2]
