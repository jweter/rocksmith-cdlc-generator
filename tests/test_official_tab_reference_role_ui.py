from __future__ import annotations

from rocksmith_cdlc_generator.official_tab_reference import (
    OfficialTabReferenceManifest,
    OfficialTabReferenceMapping,
    OfficialTabReferencePage,
)
from rocksmith_cdlc_generator.official_tab_reference_role_ui import OfficialTabReferenceRoleMixin
from rocksmith_cdlc_generator.score_source import ArrangementRole


class _FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _FakeCombo:
    def __init__(self) -> None:
        self.values: tuple[str, ...] = ()

    def configure(self, **kwargs) -> None:
        self.values = tuple(kwargs.get("values", ()))


def _manifest(*roles: ArrangementRole) -> OfficialTabReferenceManifest:
    pages = []
    for index, role in enumerate(roles, start=1):
        pages.append(
            OfficialTabReferencePage(
                page_id=f"page-{index}",
                relative_path=f"references/official-tab/pages/page-{index}.png",
                sha256="0" * 64,
                mappings=[
                    OfficialTabReferenceMapping(
                        mapping_id=f"map-{index}",
                        arrangement=role,
                        measure_start=index * 10,
                        measure_end=index * 10 + 7,
                    )
                ],
            )
        )
    return OfficialTabReferenceManifest(pages=pages)


def _harness(manifest: OfficialTabReferenceManifest, *, preview_role: str = "lead"):
    harness = OfficialTabReferenceRoleMixin()
    harness._official_tab_manifest = manifest
    harness.official_tab_role_var = _FakeVar("")
    harness.official_tab_role_combo = _FakeCombo()
    harness.fretboard_role_var = _FakeVar(preview_role)
    return harness


def _canonical_mapped_order(*roles: ArrangementRole) -> tuple[str, ...]:
    wanted = set(roles)
    return tuple(role.value for role in ArrangementRole if role in wanted)


def test_bass_only_reference_is_selectable_without_bass_arrangement_draft() -> None:
    harness = _harness(_manifest(ArrangementRole.bass), preview_role="lead")

    harness._update_official_tab_roles()

    assert harness.official_tab_role_combo.values == ("bass",)
    assert harness.official_tab_role_var.get() == "bass"
    assert harness._active_reference_role() == "bass"


def test_reference_role_selection_is_independent_from_preview_role() -> None:
    harness = _harness(
        _manifest(ArrangementRole.lead, ArrangementRole.bass),
        preview_role="lead",
    )
    harness.official_tab_role_var.set("bass")

    harness._update_official_tab_roles()
    harness.fretboard_role_var.set("lead")

    assert harness._active_reference_role() == "bass"
    assert harness.official_tab_role_combo.values == _canonical_mapped_order(
        ArrangementRole.lead,
        ArrangementRole.bass,
    )


def test_invalid_reference_role_falls_back_to_mapped_preview_role_then_first_role() -> None:
    harness = _harness(
        _manifest(ArrangementRole.rhythm, ArrangementRole.bass),
        preview_role="bass",
    )
    harness.official_tab_role_var.set("lead")

    harness._update_official_tab_roles()
    assert harness.official_tab_role_var.get() == "bass"

    harness.fretboard_role_var.set("lead")
    harness.official_tab_role_var.set("")
    harness._update_official_tab_roles()
    expected_first = _canonical_mapped_order(ArrangementRole.rhythm, ArrangementRole.bass)[0]
    assert harness.official_tab_role_var.get() == expected_first
