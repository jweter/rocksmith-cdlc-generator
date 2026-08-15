from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_edit_history import (
    load_current_arrangement_edit_history,
    redo_arrangement_edit,
    undo_arrangement_edit,
)
from .audio_playback import PlaybackUnavailable, ProjectAudioTransport
from .chord_identity_ui import ChordIdentitySongWorkspaceWindow
from .validation_dashboard_ui import ValidationDashboardPanel
from .waveform_cache import WaveformEnvelope, load_or_build_waveform


_TEXT_INPUT_WIDGET_CLASSES = {
    "Entry",
    "TEntry",
    "Text",
    "TCombobox",
    "Spinbox",
    "TSpinbox",
}
_CTRL_ALT_STATE_MASK = 0x000C


class ArrangementEditHistorySongWorkspaceWindow(ChordIdentitySongWorkspaceWindow):
    """Song Workspace with provenance-safe editing plus responsive media loading."""

    def __init__(self, parent: tk.Misc, project: Path, *, run_callback=None) -> None:
        self._media_load_generation = 0
        self._media_loading_project: Path | None = None
        super().__init__(parent, project, run_callback=run_callback)
        self._bind_transport_shortcuts()

    def set_project(self, project: Path) -> None:
        self._invalidate_pending_media_load()
        super().set_project(project)

    def destroy(self) -> None:
        self._invalidate_pending_media_load()
        super().destroy()

    def _invalidate_pending_media_load(self) -> None:
        self._media_load_generation += 1
        self._media_loading_project = None

    def _build_layout(self) -> None:
        super()._build_layout()
        self.validation_dashboard_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.insert(3, self.validation_dashboard_tab, text="Validation")
        self.validation_dashboard = ValidationDashboardPanel(self.validation_dashboard_tab)
        self.validation_dashboard.pack(fill="both", expand=True)

    def _bind_transport_shortcuts(self) -> None:
        """Bind review-oriented transport keys without stealing text-entry gestures."""

        for sequence in (
            "<space>",
            "<KeyPress-k>",
            "<KeyPress-j>",
            "<KeyPress-l>",
            "<Home>",
            "<End>",
        ):
            self.bind(sequence, self._transport_shortcut, add="+")

    @staticmethod
    def _shortcut_target_is_text_input(widget: object) -> bool:
        try:
            widget_class = str(widget.winfo_class())  # type: ignore[attr-defined]
        except (AttributeError, tk.TclError):
            return False
        return widget_class in _TEXT_INPUT_WIDGET_CLASSES

    def _transport_shortcut(self, event: tk.Event) -> str | None:
        """Dispatch one keyboard transport gesture, preserving edit/control shortcuts."""

        if self._shortcut_target_is_text_input(event.widget):
            return None
        if int(getattr(event, "state", 0)) & _CTRL_ALT_STATE_MASK:
            return None

        key = str(getattr(event, "keysym", "")).lower()
        if key in {"space", "k"}:
            self._play_pause()
        elif key == "j":
            self._seek_relative(-5.0)
        elif key == "l":
            self._seek_relative(5.0)
        elif key == "home":
            self._seek_to(0.0)
        elif key == "end":
            if self.snapshot is None:
                return None
            self._seek_to(self.snapshot.duration_seconds)
        else:
            return None
        return "break"

    def _build_timeline(self) -> None:
        super()._build_timeline()
        ttk.Label(
            self.timeline_tab,
            text=(
                "Keyboard transport: Space/K play or pause · J/L seek −/+5s · Home/End seek to song bounds. "
                "Transport keys are suspended while typing in text or selection fields."
            ),
            wraplength=1200,
        ).pack(anchor="w", pady=(4, 0))

    def _ensure_media(self) -> None:
        """Load waveform/cache and transport without blocking Tk's event thread.

        The inherited playback layer used to build the full waveform synchronously from
        refresh. Dense multi-minute songs can require enough hashing/PCM iteration to make
        Windows appear frozen. The final product workspace therefore owns the asynchronous
        boundary while preserving the same normalized-audio authority and transport types.
        """

        project = self.project.expanduser().resolve()
        if (
            self._media_project == project
            and self.transport is not None
            and self.waveform is not None
        ):
            return
        if self._media_loading_project == project:
            return

        self._close_media()
        self._media_load_generation += 1
        generation = self._media_load_generation
        self._media_loading_project = project
        self.media_status_var.set("Preparing waveform + playback in background…")

        def worker() -> None:
            waveform: WaveformEnvelope | None = None
            transport: ProjectAudioTransport | None = None
            status_message: str | None = None
            try:
                waveform = load_or_build_waveform(project)
                transport = ProjectAudioTransport(project)
            except FileNotFoundError:
                status_message = "Run normalization to enable waveform + playback"
            except (OSError, ValueError, PlaybackUnavailable) as exc:
                status_message = f"Audio preview unavailable: {exc}"

            try:
                self.after(
                    0,
                    lambda loaded_project=project,
                    loaded_generation=generation,
                    loaded_waveform=waveform,
                    loaded_transport=transport,
                    loaded_status=status_message: self._finish_media_load(
                        loaded_project,
                        loaded_generation,
                        loaded_waveform,
                        loaded_transport,
                        loaded_status,
                    ),
                )
            except tk.TclError:
                if transport is not None:
                    transport.close()

        threading.Thread(target=worker, daemon=True, name="cdlc-waveform-loader").start()

    def _finish_media_load(
        self,
        project: Path,
        generation: int,
        waveform: WaveformEnvelope | None,
        transport: ProjectAudioTransport | None,
        status_message: str | None,
    ) -> None:
        """Publish one background result only if it still belongs to the open project."""

        if generation != self._media_load_generation or project != self.project.expanduser().resolve():
            if transport is not None:
                transport.close()
            return

        self._media_loading_project = None
        if status_message is not None or waveform is None or transport is None:
            if transport is not None:
                transport.close()
            self.media_status_var.set(status_message or "Audio preview unavailable")
            self._sync_media_controls()
            self._draw_timeline()
            return

        self.waveform = waveform
        self.transport = transport
        self._media_project = project
        self.seek_scale.configure(to=max(transport.duration_seconds, 0.001))
        self.media_status_var.set(
            f"{transport.sample_rate_hz / 1000:.1f} kHz · {transport.channels} ch · normalized PCM"
        )
        self._sync_media_controls()
        self._draw_timeline()

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Accepted arrangement edit history",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.undo_edit_button = ttk.Button(
            row,
            text="Undo Accepted Edit",
            command=self._undo_accepted_edit,
            state="disabled",
        )
        self.undo_edit_button.pack(side="left")
        self.redo_edit_button = ttk.Button(
            row,
            text="Redo Accepted Edit",
            command=self._redo_accepted_edit,
            state="disabled",
        )
        self.redo_edit_button.pack(side="left", padx=(6, 0))
        self.edit_history_status_var = tk.StringVar(
            value="Accepted position, timing, technique, fingering, and chord-identity edits become reversible here."
        )
        ttk.Label(
            row,
            textvariable=self.edit_history_status_var,
            wraplength=900,
            justify="left",
        ).pack(side="left", fill="x", expand=True, padx=(14, 0))

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "validation_dashboard") and self.snapshot is not None:
            self.validation_dashboard.refresh_from_snapshot(self.snapshot)
        if hasattr(self, "undo_edit_button"):
            self._sync_edit_history_controls()

    def _sync_edit_history_controls(self) -> None:
        self.undo_edit_button.configure(state="disabled")
        self.redo_edit_button.configure(state="disabled")
        try:
            history = load_current_arrangement_edit_history(self.project)
        except (OSError, ValueError) as exc:
            self.edit_history_status_var.set(
                f"Edit history unavailable until authority is current: {exc}"
            )
            return

        if history.can_undo:
            self.undo_edit_button.configure(state="normal")
        if history.can_redo:
            self.redo_edit_button.configure(state="normal")

        applied = history.cursor
        total = len(history.transactions)
        if total == 0:
            self.edit_history_status_var.set(
                "No accepted arrangement edits have been recorded for current authority."
            )
            return
        previous = history.transactions[applied - 1].kind if applied else None
        upcoming = history.transactions[applied].kind if applied < total else None
        details = [f"{applied}/{total} accepted edit transaction(s) applied"]
        if previous is not None:
            details.append(f"undo: {previous.replace('_', ' ')}")
        if upcoming is not None:
            details.append(f"redo: {upcoming.replace('_', ' ')}")
        self.edit_history_status_var.set(" · ".join(details))

    def _undo_accepted_edit(self) -> None:
        try:
            transaction = undo_arrangement_edit(self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Arrangement Edit History", str(exc), parent=self)
            self._sync_edit_history_controls()
            return
        self.refresh()
        self.edit_history_status_var.set(
            f"Undid accepted {transaction.kind.replace('_', ' ')} edit by restoring the exact prior review authority."
        )

    def _redo_accepted_edit(self) -> None:
        try:
            transaction = redo_arrangement_edit(self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Arrangement Edit History", str(exc), parent=self)
            self._sync_edit_history_controls()
            return
        self.refresh()
        self.edit_history_status_var.set(
            f"Redid accepted {transaction.kind.replace('_', ' ')} edit by restoring the exact recorded review authority."
        )
