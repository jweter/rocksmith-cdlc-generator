from rocksmith_cdlc_generator.desktop_theme import PALETTE, configure_desktop_styles


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
