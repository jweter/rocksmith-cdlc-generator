from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_edit_history_ui import ArrangementEditHistorySongWorkspaceWindow
from .audio_output import (
    AudioOutputDevice,
    AudioOutputUnavailable,
    describe_output_devices,
    list_output_devices,
    preferred_output_device,
    select_output_device,
)
from .eof_workspace_ui import EOFWorkspaceMixin
from .review_queue_workspace_ui import ReviewQueueWorkspaceMixin
from .score_role_composition_workspace_ui import ScoreRoleCompositionWorkspaceMixin
from .timing_bpm_workspace_ui import TimingBpmWorkspaceMixin
from .track_trust_workspace_ui import TrackTrustWorkspaceMixin


class AudioOutputSongWorkspaceWindow(
    EOFWorkspaceMixin,
    ReviewQueueWorkspaceMixin,
    ScoreRoleCompositionWorkspaceMixin,
    TrackTrustWorkspaceMixin,
    TimingBpmWorkspaceMixin,
    ArrangementEditHistorySongWorkspaceWindow,
):
    """Final Song Workspace with explicit local preview-output and review routing."""

    def _build_timeline(self) -> None:
        super()._build_timeline()

        box = ttk.LabelFrame(self.timeline_tab, text="Audio output", padding=8)
        box.pack(fill="x", pady=(6, 0))
        self.audio_output_var = tk.StringVar(value="Detecting output devices…")
        self.audio_output_status_var = tk.StringVar(value="")
        self._audio_devices_by_label: dict[str, AudioOutputDevice] = {}

        ttk.Label(box, text="Preview device").pack(side="left")
        self.audio_output_combo = ttk.Combobox(
            box,
            textvariable=self.audio_output_var,
            state="readonly",
            width=58,
        )
        self.audio_output_combo.pack(side="left", padx=(8, 6))
        self.audio_output_combo.bind("<<ComboboxSelected>>", self._audio_output_changed)
        ttk.Button(box, text="Refresh devices", command=self._refresh_audio_outputs).pack(side="left", padx=(0, 6))
        ttk.Button(box, text="Diagnostics…", command=self._show_audio_output_diagnostics).pack(side="left")
        ttk.Label(
            box,
            textvariable=self.audio_output_status_var,
            wraplength=430,
            justify="left",
        ).pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.after_idle(self._refresh_audio_outputs)

    def _refresh_audio_outputs(self) -> None:
        try:
            devices = list_output_devices()
        except AudioOutputUnavailable as exc:
            self._audio_devices_by_label = {}
            self.audio_output_combo.configure(values=[])
            self.audio_output_var.set("Audio device diagnostics unavailable")
            self.audio_output_status_var.set(str(exc))
            return

        self._audio_devices_by_label = {device.label: device for device in devices}
        labels = list(self._audio_devices_by_label)
        self.audio_output_combo.configure(values=labels)
        selected = preferred_output_device(devices)
        if selected is None:
            self.audio_output_var.set("No output-capable device found")
            self.audio_output_status_var.set("Playback cannot start until Windows exposes an output-capable audio device.")
            return

        self.audio_output_var.set(selected.label)
        try:
            select_output_device(selected, persist=False)
        except AudioOutputUnavailable as exc:
            self.audio_output_status_var.set(str(exc))
            return
        source = "saved preference" if not selected.is_default else "Windows/default output"
        self.audio_output_status_var.set(f"Using {selected.name} · {source}")

    def _audio_output_changed(self, _event=None) -> None:
        selected = self._audio_devices_by_label.get(self.audio_output_var.get())
        if selected is None:
            return
        try:
            select_output_device(selected)
        except AudioOutputUnavailable as exc:
            messagebox.showerror("Song Workspace Audio", str(exc), parent=self)
            self.audio_output_status_var.set(str(exc))
            return

        # Existing RawOutputStreams are bound to their original endpoint. Recreate only
        # local preview media; musical/timing/review authority is untouched.
        self._invalidate_pending_media_load()
        self._close_media()
        self.audio_output_status_var.set(f"Using {selected.name} · saved for future sessions")
        self._ensure_media()

    def _show_audio_output_diagnostics(self) -> None:
        try:
            devices = list_output_devices()
            details = describe_output_devices(devices)
        except AudioOutputUnavailable as exc:
            details = str(exc)
        selected = self.audio_output_var.get()
        messagebox.showinfo(
            "Song Workspace Audio Diagnostics",
            f"Selected preview output:\n{selected}\n\n{details}",
            parent=self,
        )
