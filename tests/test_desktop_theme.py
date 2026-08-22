from rocksmith_cdlc_generator.design_tokens import STATUS_STYLES, status_style
from rocksmith_cdlc_generator.desktop_theme import PALETTE, configure_desktop_styles, status_dark_foreground


class FakeStyle:
    def __init__(self) -> None:
        self.configured: dict[str, dict[str, object]] = {}
        self.mapped: dict[str, dict[str, object]] = {}

    def configure(self, name: str, **options: object) -> None:
        previous = self.configured.get(name, {})
        self.configured[name] = {**previous, **options}

    def map(self, name: str, **options: object) -> None:
        previous = self.mapped.get(name, {})
        self.mapped[name] = {**previous, **options}


def test_desktop_theme_registers_core_authoring_styles() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    assert style.configured["TFrame"]["background"] == PALETTE.surface
    assert style.configured["TLabelframe"]["background"] == PALETTE.surface
    assert style.configured["Treeview"]["background"] == PALETTE.surface
    assert style.configured["TNotebook.Tab"]["foreground"] == PALETTE.text_muted
    assert style.configured["Horizontal.TProgressbar"]["background"] == PALETTE.accent


def test_primary_action_style_has_distinct_accent_and_disabled_state() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    primary = style.configured["Primary.TButton"]
    assert primary["background"] == PALETTE.accent
    assert primary["foreground"] == "#FFFFFF"
    assert ("disabled", PALETTE.border_strong) in style.mapped["Primary.TButton"]["background"]


def test_review_aid_checkbutton_is_visually_promoted() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    review_aid = style.configured["ReviewAid.TCheckbutton"]
    assert review_aid["background"] == PALETTE.accent_soft
    assert review_aid["foreground"] == PALETTE.accent_hover
    assert ("active", PALETTE.selection) in style.mapped["ReviewAid.TCheckbutton"]["background"]


def test_dark_theme_overrides_semantic_status_foregrounds_for_contrast() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    assert style.configured["Status.Pass.TLabel"]["foreground"] == PALETTE.success
    assert style.configured["Status.Warning.TLabel"]["foreground"] == PALETTE.warning
    assert style.configured["Status.Fail.TLabel"]["foreground"] == PALETTE.danger
    assert style.configured["Status.Stale.TLabel"]["foreground"] == PALETTE.text_muted
    assert style.configured["Status.ReviewRequired.TLabel"]["foreground"] == PALETTE.accent_hover
    assert style.configured["Status.Info.TLabel"]["foreground"] == PALETTE.info
    assert all(
        style.configured[name]["background"] == PALETTE.surface
        for name in (
            "Status.Pass.TLabel",
            "Status.Warning.TLabel",
            "Status.Fail.TLabel",
            "Status.Stale.TLabel",
            "Status.ReviewRequired.TLabel",
            "Status.Info.TLabel",
        )
    )


def test_status_dark_foreground_covers_every_semantic_status_state() -> None:
    """``status_dark_foreground`` is the shared helper any desktop screen must use to
    color a status label's foreground directly (rather than applying a named ttk
    style). It must classify every state ``design_tokens.STATUS_STYLES`` defines, and
    match the same dark-theme colors ``configure_desktop_styles`` registers on the
    named ``Status.*.TLabel`` ttk styles, so a label styled either way looks the same."""

    style = FakeStyle()
    configure_desktop_styles(style)

    for state, status in STATUS_STYLES.items():
        assert status_dark_foreground(state) == style.configured[status.ttk_style_name]["foreground"]


def test_status_dark_foreground_differs_from_light_status_token_for_contrast() -> None:
    """Regression for the desktop_app.py Score & Mappings role-status labels and the
    track_trust_workspace_ui.py track-trust panel label: both previously set their
    foreground directly from ``design_tokens.status_style(...).foreground``, which is
    tuned for light backgrounds and reads as low-contrast-to-illegible on this app's
    dark ``PALETTE`` (e.g. ``#1B5E20`` dark green for "pass" on ``PALETTE.surface``
    ``#151A22``). Every semantic state's dark-theme-safe color must differ from its
    light-token counterpart, proving a caller cannot accidentally get the same
    (wrong) value from either helper."""

    for state in STATUS_STYLES:
        assert status_dark_foreground(state) != status_style(state).foreground
