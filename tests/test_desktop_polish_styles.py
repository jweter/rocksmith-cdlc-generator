from rocksmith_cdlc_generator.desktop_polish import configure_polish_styles
from rocksmith_cdlc_generator.desktop_theme import PALETTE


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


def test_workspace_notebook_has_stronger_selected_tab_hierarchy() -> None:
    style = FakeStyle()
    configure_polish_styles(style)

    tab = style.configured["Workspace.TNotebook.Tab"]
    assert tab["foreground"] == PALETTE.text_muted
    assert ("selected", PALETTE.accent_soft) in style.mapped["Workspace.TNotebook.Tab"]["background"]
    assert ("selected", PALETTE.accent_hover) in style.mapped["Workspace.TNotebook.Tab"]["foreground"]


def test_workspace_tables_are_roomier_and_high_contrast() -> None:
    style = FakeStyle()
    configure_polish_styles(style)

    tree = style.configured["Workspace.Treeview"]
    heading = style.configured["Workspace.Treeview.Heading"]
    assert tree["rowheight"] == 32
    assert tree["background"] == PALETTE.surface
    assert heading["background"] == PALETTE.surface_alt
    assert heading["foreground"] == PALETTE.text


def test_transport_and_utility_actions_have_distinct_visual_weight() -> None:
    style = FakeStyle()
    configure_polish_styles(style)

    transport = style.configured["Transport.TButton"]
    utility = style.configured["Utility.TButton"]
    assert transport["background"] == PALETTE.accent_soft
    assert transport["foreground"] == PALETTE.text
    assert utility["background"] == PALETTE.surface
    assert utility["foreground"] == PALETTE.text_muted
    assert transport["background"] != utility["background"]


def test_workspace_scrollbars_and_panes_match_dark_authoring_surface() -> None:
    style = FakeStyle()
    configure_polish_styles(style)

    assert style.configured["Workspace.Vertical.TScrollbar"]["troughcolor"] == PALETTE.canvas
    assert style.configured["Workspace.Horizontal.TScrollbar"]["troughcolor"] == PALETTE.canvas
    assert ("active", PALETTE.accent) in style.mapped["Workspace.Vertical.TScrollbar"]["background"]
    assert style.configured["Workspace.TPanedwindow"]["background"] == PALETTE.border
