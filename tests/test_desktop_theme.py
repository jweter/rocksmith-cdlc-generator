from rocksmith_cdlc_generator.desktop_theme import PALETTE, configure_desktop_styles


class FakeStyle:
    def __init__(self) -> None:
        self.configured: dict[str, dict[str, object]] = {}
        self.mapped: dict[str, dict[str, object]] = {}

    def configure(self, name: str, **options: object) -> None:
        self.configured[name] = options

    def map(self, name: str, **options: object) -> None:
        self.mapped[name] = options


def test_desktop_theme_registers_core_authoring_styles() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    assert style.configured["TFrame"]["background"] == PALETTE.canvas
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


def test_status_styles_remain_registered_with_visual_theme() -> None:
    style = FakeStyle()

    configure_desktop_styles(style)

    assert "Status.Pass.TLabel" in style.configured
    assert "Status.Warning.TLabel" in style.configured
    assert "Status.Fail.TLabel" in style.configured
    assert "Status.Stale.TLabel" in style.configured
    assert "Status.ReviewRequired.TLabel" in style.configured
    assert "Status.Info.TLabel" in style.configured
