from __future__ import annotations

import inspect

from rocksmith_cdlc_generator.eof_workspace_ui import EOFWorkspaceMixin


def test_eof_reference_panel_is_packed_before_existing_timeline_content() -> None:
    source = inspect.getsource(EOFWorkspaceMixin._build_timeline)

    assert "before=existing_children[0]" in source
    assert 'text="Editor on Fire reference"' in source
    assert 'text="Open in EOF"' in source
    assert 'text="Compare alternate GP…"' in source
