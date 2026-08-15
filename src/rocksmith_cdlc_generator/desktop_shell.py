from __future__ import annotations

import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .desktop_app import APP_TITLE, DesktopApp
from .song_workspace_ui import SongWorkspaceWindow


class ProductDesktopApp(DesktopApp):
    """Product shell that keeps the project manager and Song Workspace connected."""

    def __init__(self) -> None:
        self._workspace_window: SongWorkspaceWindow | None = None
        super().__init__()
        self.title(APP_TITLE)

    def _build_menu(self) -> None:
        super()._build_menu()
        menu_name = self.cget("menu")
        menu = self.nametowidget(menu_name)
        workspace_menu = tk.Menu(menu, tearoff=False)
        workspace_menu.add_command(label="Open Song Workspace", command=self.open_song_workspace)
        workspace_menu.add_command(label="Refresh Song Workspace", command=self.refresh_song_workspace)
        menu.add_cascade(label="Workspace", menu=workspace_menu)

    def _build_layout(self) -> None:
        super()._build_layout()

        # Keep the existing project-management surface while making the actual authoring
        # workspace a prominent first-class action in the packaged application.
        children = self.winfo_children()
        before = children[-1] if children else None
        bar = ttk.Frame(self, padding=(12, 0, 12, 6))
        pack_options = {"fill": "x"}
        if before is not None:
            pack_options["before"] = before
        bar.pack(**pack_options)
        ttk.Label(
            bar,
            text="Song Workspace is the main review and authoring surface for the open project.",
        ).pack(side="left")
        ttk.Button(bar, text="Open Song Workspace", command=self.open_song_workspace).pack(side="right")

        # Until explicit safe score replacement exists, do not advertise a capability
        # the engine intentionally refuses. This also resolves the misleading desktop
        # label without weakening the immutable-score contract.
        self._rename_button(self, "Register / Replace Score", "Register Score…")

    def _rename_button(self, widget: tk.Misc, old: str, new: str) -> None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button) and str(child.cget("text")) == old:
                child.configure(text=new)
            self._rename_button(child, old, new)

    def _run_background(self, label: str, operation, on_success=None) -> None:
        """Run one desktop operation without letting callback lifetime wedge the GUI."""

        if self._busy:
            return
        self._set_busy(True, label)
        self._log(label)

        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:  # GUI boundary: retain exception beyond the except scope.
                details = traceback.format_exc()
                self.after(
                    0,
                    lambda error=exc, traceback_text=details: self._background_failed(
                        error, traceback_text
                    ),
                )
                return
            self.after(0, lambda value=result: self._background_succeeded(value, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def load_project(self, project: Path) -> None:
        super().load_project(project)
        if self.project is not None and self.project == project.expanduser().resolve():
            self.refresh_song_workspace()

    def refresh_project(self) -> None:
        super().refresh_project()
        self.refresh_song_workspace()

    def open_song_workspace(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        if self._workspace_window is not None and self._workspace_window.winfo_exists():
            self._workspace_window.set_project(self.project)
            self._workspace_window.deiconify()
            self._workspace_window.lift()
            self._workspace_window.focus_force()
            return

        self._workspace_window = SongWorkspaceWindow(
            self,
            self.project,
            run_callback=self.run_automatic_steps,
        )
        self._workspace_window.protocol("WM_DELETE_WINDOW", self._close_song_workspace)

    def _close_song_workspace(self) -> None:
        if self._workspace_window is not None and self._workspace_window.winfo_exists():
            self._workspace_window.destroy()
        self._workspace_window = None

    def refresh_song_workspace(self) -> None:
        window = self._workspace_window
        if window is None or not window.winfo_exists() or self.project is None:
            return
        if window.project != self.project:
            window.set_project(self.project)
        else:
            window.refresh()


def main() -> None:
    app = ProductDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
