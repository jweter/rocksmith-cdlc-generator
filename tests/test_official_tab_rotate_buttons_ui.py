"""Regression coverage for the Codex P2 finding on merged PR #459.

The Official TAB reference viewer's "Rotate ⟲" (counter-clockwise glyph) and
"Rotate ⟳" (clockwise glyph) toolbar buttons passed deltas that were swapped
relative to their labels: clicking the counter-clockwise button visibly
rotated the page image clockwise, and vice versa. ``image_rotation.py``
documents (and ``test_image_rotation.py`` pins) that a *positive*
quarter-turn is counter-clockwise, matching how
``Image.transpose(Image.Transpose.ROTATE_90)`` actually behaves in Pillow --
this was verified directly against Pillow's runtime behavior, not assumed
from the constant's name. The bug was entirely in the button-to-delta wiring
in ``_build_arrangement_preview`` (``official_tab_reference_ui.py``): the
counter-clockwise-labelled button passed ``-1`` and the clockwise-labelled
button passed ``+1``.

These tests exercise the *real* button construction and the real
``_rotate_official_tab_page``/``rotate_image_quarter_turns`` pipeline against
lightweight recording stand-ins for the ``tkinter``/``ttk`` widget classes,
following the no-display-server convention established in
``tests/test_desktop_score_tab_layout.py``. They pin the direction with an
asymmetric test image (a single marker pixel in one corner) so a swapped
sign -- not just "some rotation happened" -- would fail the test.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from rocksmith_cdlc_generator import official_tab_reference_ui
from rocksmith_cdlc_generator.image_rotation import rotate_image_quarter_turns
from rocksmith_cdlc_generator.official_tab_reference import (
    load_reference_manifest,
    register_reference_page,
    resolve_reference_image,
)


class _FakeVar:
    def __init__(self, value: object = None, **_kwargs: object) -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value


class _FakeWidget:
    """Records construction args/children without needing a real Tk root."""

    def __init__(self, master: "_FakeWidget | None" = None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        if master is not None:
            master.children.append(self)

    def winfo_children(self) -> list["_FakeWidget"]:
        return list(self.children)

    def cget(self, name: str) -> object:
        return self.kwargs.get(name)

    def configure(self, **kwargs: object) -> None:
        self.kwargs.update(kwargs)

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _record(*_args: object, **_kwargs: object):
            return None

        self.__dict__[name] = _record
        return _record


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeButton(_FakeWidget):
    pass


class _FakeCombobox(_FakeWidget):
    pass


class _FakeScrollbar(_FakeWidget):
    pass


class _FakeCanvas(_FakeWidget):
    pass


class _FakeBase:
    """Stand-in for the ancestor class that supplies the EOF live-view widgets
    ``OfficialTabReferenceMixin._build_arrangement_preview`` builds its toolbar
    onto, without pulling in the entire real desktop widget tree."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def set_project(self, project: Path) -> None:
        pass

    def _build_arrangement_preview(self) -> None:
        toolbar = _FakeFrame()
        live_box = _FakeFrame()
        self.eof_live_role_combo = _FakeWidget(master=toolbar)
        self.eof_tab_canvas = _FakeWidget(master=live_box)
        self.eof_highway_canvas = _FakeWidget()


class _Harness(official_tab_reference_ui.OfficialTabReferenceMixin, _FakeBase):
    pass


def _build_nav_buttons(monkeypatch) -> tuple[_Harness, dict[str, _FakeButton]]:
    """Build the real toolbar via the real mixin code and capture its buttons."""

    monkeypatch.setattr(official_tab_reference_ui.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(official_tab_reference_ui.ttk, "Label", _FakeLabel)
    monkeypatch.setattr(official_tab_reference_ui.ttk, "Button", _FakeButton)
    monkeypatch.setattr(official_tab_reference_ui.ttk, "Combobox", _FakeCombobox)
    monkeypatch.setattr(official_tab_reference_ui.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(official_tab_reference_ui.tk, "Canvas", _FakeCanvas)
    monkeypatch.setattr(official_tab_reference_ui.tk, "StringVar", _FakeVar)

    harness = _Harness()
    harness._build_arrangement_preview()
    # Avoid needing a full fake Tk Canvas render pipeline; the state change we
    # care about (the persisted rotation) already happened by the time this
    # is called, and the actual pixel effect is verified separately below via
    # the same production resolve+rotate call the real draw path uses.
    harness._draw_official_tab_reference = lambda *args, **kwargs: None

    nav = harness.official_tab_reference_frame.children[1]
    buttons = {child.kwargs.get("text"): child for child in nav.children}
    assert "Rotate ⟲" in buttons and "Rotate ⟳" in buttons
    return harness, buttons


def _register_asymmetric_page(tmp_path: Path) -> tuple[Path, str]:
    """Register a page whose single marker pixel makes each of the four
    quarter-turn orientations land in a visually distinct, unambiguous spot."""

    project = tmp_path / "song"
    # PNG (not JPEG) so the single-pixel marker survives lossless round-tripping
    # exactly -- a JPEG would blur it via chroma subsampling/quantization and
    # make the pixel-level assertions below flaky rather than deterministic.
    source = tmp_path / "camera" / "page-01.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (6, 4), (10, 10, 10))
    image.putpixel((0, 0), (255, 0, 0))  # marker at the top-left corner
    image.save(source)

    hit = register_reference_page(
        project,
        source,
        arrangement="lead",
        measure_start=1,
        measure_end=8,
        printed_page="1",
    )
    return project, hit.page.page_id


def test_rotate_ccw_button_rotates_the_displayed_image_counter_clockwise(monkeypatch, tmp_path: Path) -> None:
    project, page_id = _register_asymmetric_page(tmp_path)
    harness, buttons = _build_nav_buttons(monkeypatch)
    harness.project = project
    manifest = load_reference_manifest(project)
    harness._official_tab_manifest = manifest
    hit = next(h for h in manifest.pages if h.page_id == page_id)
    mapping = hit.mappings[0]
    from rocksmith_cdlc_generator.official_tab_reference import OfficialTabReferenceHit

    harness._official_tab_current_hit = OfficialTabReferenceHit(hit, mapping)

    buttons["Rotate ⟲"].kwargs["command"]()

    updated_page = next(p for p in harness._official_tab_manifest.pages if p.page_id == page_id)
    # A single click of the counter-clockwise button must be exactly +1
    # quarter turn (the convention `image_rotation.py` and its tests pin as
    # counter-clockwise), not -1/3.
    assert updated_page.rotation_quarter_turns == 1

    # Mirror the real draw path (`_draw_official_tab_reference`): resolve the
    # registered source image, then apply the persisted rotation via the same
    # `rotate_image_quarter_turns` helper the viewer renders with.
    path = resolve_reference_image(project, updated_page)
    with Image.open(path) as opened:
        rotated = rotate_image_quarter_turns(opened.convert("RGB"), updated_page.rotation_quarter_turns)
    assert rotated.size == (4, 6)
    # The marker that started in the top-left corner must now sit in the
    # bottom-left corner -- the top edge has swung to the left, as it does
    # under a real counter-clockwise turn.
    assert rotated.getpixel((0, 5)) == (255, 0, 0)


def test_rotate_cw_button_rotates_the_displayed_image_clockwise(monkeypatch, tmp_path: Path) -> None:
    project, page_id = _register_asymmetric_page(tmp_path)
    harness, buttons = _build_nav_buttons(monkeypatch)
    harness.project = project
    manifest = load_reference_manifest(project)
    harness._official_tab_manifest = manifest
    hit = next(h for h in manifest.pages if h.page_id == page_id)
    mapping = hit.mappings[0]
    from rocksmith_cdlc_generator.official_tab_reference import OfficialTabReferenceHit

    harness._official_tab_current_hit = OfficialTabReferenceHit(hit, mapping)

    buttons["Rotate ⟳"].kwargs["command"]()

    updated_page = next(p for p in harness._official_tab_manifest.pages if p.page_id == page_id)
    # A single click of the clockwise button must be exactly -1 quarter turn,
    # which normalizes to 3 -- not +1.
    assert updated_page.rotation_quarter_turns == 3

    path = resolve_reference_image(project, updated_page)
    with Image.open(path) as opened:
        rotated = rotate_image_quarter_turns(opened.convert("RGB"), updated_page.rotation_quarter_turns)
    assert rotated.size == (4, 6)
    # The marker that started in the top-left corner must now sit in the
    # top-right corner -- the left edge has swung to the top, as it does
    # under a real clockwise turn.
    assert rotated.getpixel((3, 0)) == (255, 0, 0)
