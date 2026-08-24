"""Regression coverage for desktop modal ownership (#304/#305).

Windows can place an unowned Tk message box behind the main application window
or on another monitor, making a blocked workflow look like a frozen process.
Every message box in the base desktop shell must therefore name its owning
window explicitly.  The New Project validation warning intentionally belongs
to its child dialog; all other dialogs belong to the main DesktopApp.
"""

from __future__ import annotations

import ast
import inspect

from rocksmith_cdlc_generator import desktop_app, desktop_shell, diagnostic_guided_desktop


def test_every_desktop_messagebox_has_an_explicit_parent() -> None:
    source = inspect.getsource(desktop_app.DesktopApp)
    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "messagebox"
    ]

    assert calls, "DesktopApp should still contain user-facing message boxes"
    missing = [
        getattr(call.func, "attr", "<unknown>")
        for call in calls
        if not any(keyword.arg == "parent" for keyword in call.keywords)
    ]
    assert missing == []


def test_main_shell_dialogs_are_parented_to_self() -> None:
    source = inspect.getsource(desktop_app.DesktopApp)
    tree = ast.parse(source)

    parents = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "messagebox"
        ):
            continue
        parent = next(keyword.value for keyword in node.keywords if keyword.arg == "parent")
        parents.append(parent)

    assert any(isinstance(parent, ast.Name) and parent.id == "dialog" for parent in parents)
    assert all(
        isinstance(parent, ast.Name) and parent.id in {"self", "dialog"}
        for parent in parents
    )


def test_primary_desktop_shell_modules_never_create_unowned_messageboxes() -> None:
    """Cover the real shipped shell, including subclass-only launcher/diagnostic paths."""

    for module in (desktop_app, desktop_shell, diagnostic_guided_desktop):
        tree = ast.parse(inspect.getsource(module))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "messagebox"
        ]
        missing = [
            f"{module.__name__}:{getattr(call.func, 'attr', '<unknown>')}:{call.lineno}"
            for call in calls
            if not any(keyword.arg == "parent" for keyword in call.keywords)
        ]
        assert missing == []
