from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.design_tokens import (
    FONT_FAMILY,
    SPACING_UNIT_PX,
    STATUS_STYLES,
    TYPOGRAPHY,
    StatusState,
    configure_ttk_status_styles,
    format_status,
    spacing,
    status_style,
)


def test_typography_scale_uses_the_single_shared_font_family() -> None:
    assert TYPOGRAPHY, "typography scale must not be empty"
    for style in TYPOGRAPHY.values():
        assert style.family == FONT_FAMILY
        assert style.size > 0


def test_typography_scale_sizes_are_strictly_increasing_with_named_order() -> None:
    ordered_names = ["caption", "body", "subheading", "heading", "display"]
    sizes = [TYPOGRAPHY[name].size for name in ordered_names]
    assert sizes == sorted(sizes)
    assert len(set(sizes)) == len(sizes)


def test_spacing_scale_is_a_consistent_multiple_of_the_base_unit() -> None:
    values = [spacing(name) for name in ("xs", "sm", "md", "lg", "xl")]
    assert values == sorted(values)
    assert len(set(values)) == len(values)
    for value in values:
        assert value % SPACING_UNIT_PX == 0


def test_every_semantic_status_has_a_distinct_label_and_symbol() -> None:
    labels = [s.label for s in STATUS_STYLES.values()]
    symbols = [s.symbol for s in STATUS_STYLES.values()]
    assert len(labels) == len(set(labels)), "status labels must be unique"
    assert len(symbols) == len(set(symbols)), "status symbols must be unique"
    for state, style in STATUS_STYLES.items():
        assert style.state == state
        assert style.label
        assert style.symbol


def test_status_format_never_conveys_state_by_color_alone() -> None:
    # The formatted text must carry the meaning on its own -- color is additive only.
    for style in STATUS_STYLES.values():
        text = style.format()
        assert style.symbol in text
        assert style.label in text


def test_stale_status_is_visually_distinguished_beyond_color() -> None:
    stale = status_style("stale")
    # STALE must be unmistakable even without color: italic slant is the second,
    # color-independent signal (see docstring / issue #305's "never color-alone" rule).
    assert stale.slant == "italic"
    other_states: list[StatusState] = ["pass", "warning", "fail", "review_required"]
    assert all(status_style(state).slant != "italic" for state in other_states)


def test_format_status_includes_optional_detail() -> None:
    text = format_status("fail", "97 unmapped notes")
    assert text.startswith("✗ FAIL")
    assert "97 unmapped notes" in text


def test_type_style_as_tuple_matches_tk_font_spec_shape() -> None:
    body = TYPOGRAPHY["body"]
    assert body.as_tuple() == (FONT_FAMILY, body.size)

    heading = TYPOGRAPHY["heading"]
    assert heading.as_tuple() == (FONT_FAMILY, heading.size, "bold")

    stale = status_style("stale")
    from rocksmith_cdlc_generator.design_tokens import TypeStyle

    stale_font = TypeStyle(size=10, weight=stale.weight, slant=stale.slant)
    assert stale_font.as_tuple() == (FONT_FAMILY, 10, "bold italic")


def test_configure_ttk_status_styles_calls_configure_once_per_status() -> None:
    calls: list[tuple[str, dict]] = []

    class FakeTtkStyle:
        def configure(self, name: str, **options: object) -> None:
            calls.append((name, options))

    configure_ttk_status_styles(FakeTtkStyle())

    assert len(calls) == len(STATUS_STYLES)
    names = {name for name, _ in calls}
    assert names == {style.ttk_style_name for style in STATUS_STYLES.values()}
    for _, options in calls:
        assert "foreground" in options
        assert "font" in options


def test_status_style_lookup_rejects_unknown_state() -> None:
    with pytest.raises(KeyError):
        status_style("does_not_exist")  # type: ignore[arg-type]
