from __future__ import annotations

import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .audio_output_ui import AudioOutputSongWorkspaceWindow
from .desktop_app import APP_TITLE, DesktopApp
from .desktop_xml_export import ArrangementName, export_project_arrangement_xml
from .desktop_xml_export_window import RocksmithXmlExportWindow
from .metadata_cover_window import MetadataCoverWindow
from .product_reality_ui import ProductRealityRecorderWindow
from .tone_regions_window import ToneRegionsWindow


class ProductDesktopApp(DesktopApp):
    """Product shell that keeps the project manager and Song Workspace connected."""

    def __init__(self) -> None:
        self._workspace_window: AudioOutputSongWorkspaceWindow | None = None
        self._product_reality_window: ProductRealityRecorderWindow | None = None
        self._metadata_cover_window: MetadataCoverWindow | None = None
        self._tone_regions_window: ToneRegionsWindow | None = None
        self._xml_export_window: RocksmithXmlExportWindow | None = None
        super().__init__()
        self.title(APP_TITLE)

    def _build_menu(self) -> None:
        super()._build_menu()
        menu_name = self.cget("menu")
        menu = self.nametowidget(menu_name)
        workspace_menu = tk.Menu(menu, tearoff=False)
        workspace_menu.add_command(label="Open Song Workspace", command=self.open_song_workspace)
        workspace_menu.add_command(label="Refresh Song Workspace", command=self.refresh_song_workspace)
        workspace_menu.add_separator()
        workspace_menu.add_command(label="Metadata & Cover…", command=self.open_metadata_cover)
        workspace_menu.add_command(label="Tones & Regions…", command=self.open_tone_regions)
        workspace_menu.add_command(label="Rocksmith XML Export…", command=self.open_xml_export)
        workspace_menu.add_separator()
        workspace_menu.add_command(
            label="Product Reality Gate Recorder",
            command=self.open_product_reality_recorder,
        )
        menu.add_cascade(label="Workspace", menu=workspace_menu)

    def _build_layout(self) -> None:
        super()._build_layout()
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
        self._rename_button(self, "Register / Replace Score", "Register Score…")

    def _rename_button(self, widget: tk.Misc, old: str, new: str) -> None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button) and str(child.cget("text")) == old:
                child.configure(text=new)
            self._rename_button(child, old, new)

    def _run_background(self, label: str, operation, on_success=None) -> None:
        if self._busy:
            return
        self._set_busy(True, label)
        self._log(label)

        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:
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
            self.refresh_metadata_cover()
            self.refresh_tone_regions()
            self.refresh_xml_export()
            self.refresh_product_reality_recorder()

    def refresh_project(self) -> None:
        super().refresh_project()
        self.refresh_song_workspace()
        self.refresh_metadata_cover()
        self.refresh_tone_regions()
        self.refresh_xml_export()
        self.refresh_product_reality_recorder()

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

        self._workspace_window = AudioOutputSongWorkspaceWindow(
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

    def open_metadata_cover(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        window = self._metadata_cover_window
        if window is not None and window.winfo_exists():
            window.set_project(self.project)
            window.deiconify()
            window.lift()
            window.focus_force()
            return
        self._metadata_cover_window = MetadataCoverWindow(self, self.project)
        self._metadata_cover_window.protocol("WM_DELETE_WINDOW", self._close_metadata_cover)

    def _close_metadata_cover(self) -> None:
        if self._metadata_cover_window is not None and self._metadata_cover_window.winfo_exists():
            self._metadata_cover_window.destroy()
        self._metadata_cover_window = None

    def refresh_metadata_cover(self) -> None:
        window = self._metadata_cover_window
        if window is None or not window.winfo_exists() or self.project is None:
            return
        if window.project != self.project:
            window.set_project(self.project)
        else:
            window.refresh()

    def open_tone_regions(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        window = self._tone_regions_window
        if window is not None and window.winfo_exists():
            window.set_project(self.project)
            window.deiconify()
            window.lift()
            window.focus_force()
            return
        self._tone_regions_window = ToneRegionsWindow(self, self.project)
        self._tone_regions_window.protocol("WM_DELETE_WINDOW", self._close_tone_regions)

    def _close_tone_regions(self) -> None:
        if self._tone_regions_window is not None and self._tone_regions_window.winfo_exists():
            self._tone_regions_window.destroy()
        self._tone_regions_window = None

    def refresh_tone_regions(self) -> None:
        window = self._tone_regions_window
        if window is None or not window.winfo_exists() or self.project is None:
            return
        if window.project != self.project:
            window.set_project(self.project)
        else:
            window.refresh()

    def open_xml_export(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        window = self._xml_export_window
        if window is not None and window.winfo_exists():
            window.set_project(self.project)
            window.deiconify()
            window.lift()
            window.focus_force()
            return
        self._xml_export_window = RocksmithXmlExportWindow(
            self,
            self.project,
            export_request=self._request_xml_export,
        )
        self._xml_export_window.protocol("WM_DELETE_WINDOW", self._close_xml_export)

    def _close_xml_export(self) -> None:
        if self._xml_export_window is not None and self._xml_export_window.winfo_exists():
            self._xml_export_window.destroy()
        self._xml_export_window = None

    def refresh_xml_export(self) -> None:
        window = self._xml_export_window
        if window is None or not window.winfo_exists() or self.project is None:
            return
        if window.project != self.project:
            window.set_project(self.project)

    def _request_xml_export(self, arrangement: ArrangementName, on_success) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        project = self.project

        def completed(outputs: dict[str, Path]) -> None:
            on_success(outputs)
            self.refresh_song_workspace()
            self.refresh_project()

        self._run_background(
            f"Exporting {arrangement.capitalize()} Rocksmith XML",
            lambda: export_project_arrangement_xml(project, arrangement=arrangement),
            completed,
        )

    def open_product_reality_recorder(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        window = self._product_reality_window
        if window is not None and window.winfo_exists():
            window.set_project(self.project)
            window.deiconify()
            window.lift()
            window.focus_force()
            return
        self._product_reality_window = ProductRealityRecorderWindow(self, self.project)
        self._product_reality_window.protocol(
            "WM_DELETE_WINDOW", self._close_product_reality_recorder
        )

    def _close_product_reality_recorder(self) -> None:
        if self._product_reality_window is not None and self._product_reality_window.winfo_exists():
            self._product_reality_window.destroy()
        self._product_reality_window = None

    def refresh_product_reality_recorder(self) -> None:
        window = self._product_reality_window
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
