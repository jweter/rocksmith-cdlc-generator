from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .desktop_theme import PALETTE
from .eof_measure_review import measure_index_for_time
from .official_tab_reference import (
    OfficialTabReferenceHit,
    OfficialTabReferenceManifest,
    load_reference_manifest,
    reference_for_measure,
    reference_hits_for_role,
    register_reference_page,
    remove_reference_mapping,
    resolve_reference_image,
    seek_seconds_for_measure,
)
from .score_source import ArrangementRole


class _ReferenceMappingDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        role: str,
        first_measure: int,
        last_measure: int,
    ) -> None:
        super().__init__(parent)
        self.title("Map official TAB page")
        self.resizable(False, False)
        self.transient(parent)
        self.result: tuple[ArrangementRole, int, int, str | None] | None = None

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                "Map this private page image onto the score. The first viewer maps the whole page; "
                "future region tools can narrow individual systems without changing musical authority."
            ),
            wraplength=520,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Arrangement").grid(row=1, column=0, sticky="w", pady=4)
        self.role_var = tk.StringVar(value=role if role in {item.value for item in ArrangementRole} else "lead")
        ttk.Combobox(
            frame,
            textvariable=self.role_var,
            values=tuple(item.value for item in ArrangementRole),
            state="readonly",
            width=16,
        ).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="First score bar").grid(row=2, column=0, sticky="w", pady=4)
        self.first_var = tk.StringVar(value=str(max(first_measure, 1)))
        ttk.Spinbox(frame, from_=1, to=10000, width=12, textvariable=self.first_var).grid(
            row=2, column=1, sticky="w", pady=4
        )

        ttk.Label(frame, text="Last score bar").grid(row=3, column=0, sticky="w", pady=4)
        self.last_var = tk.StringVar(value=str(max(last_measure, first_measure, 1)))
        ttk.Spinbox(frame, from_=1, to=10000, width=12, textvariable=self.last_var).grid(
            row=3, column=1, sticky="w", pady=4
        )

        ttk.Label(frame, text="Printed page label (optional)").grid(row=4, column=0, sticky="w", pady=4)
        self.page_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.page_var, width=24).grid(row=4, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Add Reference", command=self._accept).pack(side="right", padx=(0, 8))

        frame.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.after_idle(self._center_on_parent)

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()
            parent = self.master
            x = parent.winfo_rootx() + max((parent.winfo_width() - self.winfo_width()) // 2, 0)
            y = parent.winfo_rooty() + max((parent.winfo_height() - self.winfo_height()) // 2, 0)
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            return

    def _accept(self) -> None:
        try:
            role = ArrangementRole(self.role_var.get())
            first = int(self.first_var.get())
            last = int(self.last_var.get())
            if first < 1 or last < first:
                raise ValueError("Last score bar must be greater than or equal to first score bar.")
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return
        page = self.page_var.get().strip() or None
        self.result = (role, first, last, page)
        self.destroy()


class OfficialTabReferenceMixin:
    """Project-local official TAB image viewer synchronized to score bars and playback."""

    def __init__(self, *args, **kwargs) -> None:
        self._official_tab_manifest = OfficialTabReferenceManifest()
        self._official_tab_error: str | None = None
        self._official_tab_current_hit: OfficialTabReferenceHit | None = None
        self._official_tab_manual_key: tuple[str, str] | None = None
        self._official_tab_choice_map: dict[str, OfficialTabReferenceHit] = {}
        self._official_tab_photo = None
        self._official_tab_zoom = 1.0
        self._official_tab_visible = False
        self._official_tab_user_view_choice: bool | None = None
        self._official_tab_last_render_key: tuple[object, ...] | None = None
        self._official_tab_lower_label = None
        super().__init__(*args, **kwargs)

    def set_project(self, project: Path) -> None:
        # The desktop shell can reuse one workspace window for another project. Restore
        # the normal lower-pane geometry before discarding the previous project's viewer
        # state so a reference page cannot remain visibly packed into the next project.
        if hasattr(self, "official_tab_reference_frame"):
            self._set_official_tab_visible(False, user_choice=False)
        self._official_tab_manifest = OfficialTabReferenceManifest()
        self._official_tab_error = None
        self._official_tab_current_hit = None
        self._official_tab_manual_key = None
        self._official_tab_choice_map = {}
        self._official_tab_photo = None
        self._official_tab_zoom = 1.0
        self._official_tab_visible = False
        self._official_tab_user_view_choice = None
        self._official_tab_last_render_key = None
        super().set_project(project)

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        if not hasattr(self, "eof_tab_canvas") or not hasattr(self, "eof_highway_canvas"):
            return

        live_box = self.eof_tab_canvas.master
        toolbar = self.eof_live_role_combo.master
        self.official_tab_toggle_button = ttk.Button(
            toolbar,
            text="Show Official TAB",
            command=self._toggle_official_tab_view,
        )
        self.official_tab_toggle_button.pack(side="right", padx=(8, 0))

        for child in live_box.winfo_children():
            if not isinstance(child, ttk.Label):
                continue
            try:
                text = str(child.cget("text"))
            except tk.TclError:
                continue
            if text.startswith("Perspective fretboard"):
                self._official_tab_lower_label = child
                break

        self.official_tab_reference_frame = ttk.Frame(live_box)
        header = ttk.Frame(self.official_tab_reference_frame)
        header.pack(fill="x", pady=(0, 4))

        self.official_tab_status_var = tk.StringVar(value="No official TAB reference registered for this project.")
        ttk.Label(header, textvariable=self.official_tab_status_var, justify="left").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(header, text="Add page…", command=self._add_official_tab_page).pack(side="right", padx=(6, 0))
        ttk.Button(header, text="Remove mapping", command=self._remove_official_tab_mapping).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(header, text="Seek page start", command=self._seek_official_tab_start).pack(
            side="right", padx=(6, 0)
        )

        nav = ttk.Frame(self.official_tab_reference_frame)
        nav.pack(fill="x", pady=(0, 4))
        ttk.Button(nav, text="◀ Page", command=lambda: self._step_official_tab_reference(-1)).pack(side="left")
        self.official_tab_choice_var = tk.StringVar(value="")
        self.official_tab_choice_combo = ttk.Combobox(
            nav,
            textvariable=self.official_tab_choice_var,
            state="readonly",
            width=52,
        )
        self.official_tab_choice_combo.pack(side="left", padx=(6, 6))
        self.official_tab_choice_combo.bind("<<ComboboxSelected>>", self._official_tab_choice_changed)
        ttk.Button(nav, text="Page ▶", command=lambda: self._step_official_tab_reference(1)).pack(side="left")
        ttk.Button(nav, text="Zoom −", command=lambda: self._change_official_tab_zoom(0.8)).pack(side="right")
        ttk.Button(nav, text="Zoom +", command=lambda: self._change_official_tab_zoom(1.25)).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(nav, text="Fit width", command=self._fit_official_tab_width).pack(side="right", padx=(6, 0))

        canvas_box = ttk.Frame(self.official_tab_reference_frame)
        canvas_box.pack(fill="both", expand=True)
        self.official_tab_canvas = tk.Canvas(
            canvas_box,
            height=195,
            background=PALETTE.canvas,
            highlightthickness=1,
            highlightbackground=PALETTE.border_strong,
        )
        yscroll = ttk.Scrollbar(canvas_box, orient="vertical", command=self.official_tab_canvas.yview)
        xscroll = ttk.Scrollbar(canvas_box, orient="horizontal", command=self.official_tab_canvas.xview)
        self.official_tab_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.official_tab_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        canvas_box.rowconfigure(0, weight=1)
        canvas_box.columnconfigure(0, weight=1)
        self.official_tab_canvas.bind("<Configure>", lambda _event: self._draw_official_tab_reference())
        self.official_tab_canvas.bind("<Button-1>", lambda _event: self._seek_official_tab_start())

    def refresh(self) -> None:
        super().refresh()
        try:
            self._official_tab_manifest = load_reference_manifest(self.project, verify_files=True)
            self._official_tab_error = None
        except Exception as exc:
            self._official_tab_manifest = OfficialTabReferenceManifest()
            self._official_tab_error = str(exc)
            self._official_tab_current_hit = None
            self._official_tab_last_render_key = None
        if self._official_tab_manifest.pages and self._official_tab_user_view_choice is None:
            self._set_official_tab_visible(True, user_choice=False)
        self._sync_official_tab_reference(force=True)

    def _poll_playback(self) -> None:
        super()._poll_playback()
        if self._official_tab_visible:
            self._sync_official_tab_reference()

    def _seek_to(self, seconds: float) -> None:
        super()._seek_to(seconds)
        if hasattr(self, "official_tab_status_var"):
            self._sync_official_tab_reference()

    def _eof_live_role_changed(self, _event=None) -> None:
        super()._eof_live_role_changed(_event)
        self._official_tab_manual_key = None
        self._sync_official_tab_reference(force=True)

    def _toggle_official_tab_view(self) -> None:
        self._set_official_tab_visible(not self._official_tab_visible, user_choice=True)

    def _set_official_tab_visible(self, visible: bool, *, user_choice: bool) -> None:
        if not hasattr(self, "official_tab_reference_frame"):
            return
        self._official_tab_visible = bool(visible)
        if user_choice:
            self._official_tab_user_view_choice = self._official_tab_visible
        label = self._official_tab_lower_label
        if self._official_tab_visible:
            self.eof_highway_canvas.pack_forget()
            if label is not None:
                label.configure(text="Official TAB reference · local project evidence")
                self.official_tab_reference_frame.pack(fill="x", expand=False, pady=(3, 0), after=label)
            else:
                self.official_tab_reference_frame.pack(fill="x", expand=False, pady=(3, 0))
            self.official_tab_toggle_button.configure(text="Show Highway")
            self._sync_official_tab_reference(force=True)
        else:
            self.official_tab_reference_frame.pack_forget()
            if label is not None:
                label.configure(text="Perspective fretboard · upcoming physical positions use the same playback clock")
                self.eof_highway_canvas.pack(fill="x", expand=False, pady=(3, 0), after=label)
            else:
                self.eof_highway_canvas.pack(fill="x", expand=False, pady=(3, 0))
            self.official_tab_toggle_button.configure(text="Show Official TAB")
            self._draw_eof_highway()

    def _active_reference_role(self) -> str:
        if hasattr(self, "fretboard_role_var"):
            value = self.fretboard_role_var.get()
            if value in {role.value for role in ArrangementRole}:
                return value
        return "lead"

    def _current_reference_measure(self) -> int | None:
        measures = getattr(self, "_eof_measure_windows", [])
        if not measures:
            return None
        when = float(getattr(self, "_selected_time", None) or 0.0)
        index = measure_index_for_time(measures, when)
        if index is None:
            return None
        return measures[index].number

    @staticmethod
    def _hit_key(hit: OfficialTabReferenceHit) -> tuple[str, str]:
        return hit.page.page_id, hit.mapping.mapping_id

    def _sync_official_tab_reference(self, *, force: bool = False) -> None:
        if not hasattr(self, "official_tab_status_var"):
            return
        if self._official_tab_error:
            self.official_tab_status_var.set(f"Official TAB unavailable: {self._official_tab_error}")
            self._official_tab_current_hit = None
            self._update_official_tab_choices([])
            if self._official_tab_visible:
                self._draw_official_tab_reference(force=True)
            return

        role = self._active_reference_role()
        hits = reference_hits_for_role(self._official_tab_manifest, role)
        self._update_official_tab_choices(hits)
        measure = self._current_reference_measure()
        hit = (
            reference_for_measure(self._official_tab_manifest, role, measure)
            if measure is not None
            else None
        )
        if hit is not None:
            self._official_tab_manual_key = self._hit_key(hit)
        elif self._official_tab_manual_key is not None:
            hit = next((item for item in hits if self._hit_key(item) == self._official_tab_manual_key), None)
        if hit is None and hits:
            hit = hits[0]
            self._official_tab_manual_key = self._hit_key(hit)

        self._official_tab_current_hit = hit
        if hit is None:
            if measure is None:
                self.official_tab_status_var.set(f"No {role.title()} official TAB page mapped yet. Add a page to begin.")
            else:
                self.official_tab_status_var.set(
                    f"No {role.title()} official TAB mapping covers bar {measure}. Add or select a reference page."
                )
            self.official_tab_choice_var.set("")
        else:
            label = next((text for text, item in self._official_tab_choice_map.items() if self._hit_key(item) == self._hit_key(hit)), hit.label)
            self.official_tab_choice_var.set(label)
            coverage = f"bars {hit.mapping.measure_start}-{hit.mapping.measure_end}"
            current = f" · current bar {measure}" if measure is not None else ""
            outside = " · current bar is outside this mapping" if measure is not None and not (
                hit.mapping.measure_start <= measure <= hit.mapping.measure_end
            ) else ""
            self.official_tab_status_var.set(
                f"{hit.page.source_label} · {hit.mapping.arrangement.value.title()} · {coverage}{current}{outside} · "
                f"SHA {hit.page.sha256[:12]}"
            )

        if self._official_tab_visible:
            self._draw_official_tab_reference(force=force)

    def _update_official_tab_choices(self, hits: list[OfficialTabReferenceHit]) -> None:
        mapping: dict[str, OfficialTabReferenceHit] = {}
        for hit in hits:
            label = hit.label
            if label in mapping:
                label = f"{label} · {hit.page.sha256[:8]}"
            mapping[label] = hit
        self._official_tab_choice_map = mapping
        if hasattr(self, "official_tab_choice_combo"):
            self.official_tab_choice_combo.configure(values=list(mapping))

    def _draw_official_tab_reference(self, *, force: bool = False) -> None:
        if not hasattr(self, "official_tab_canvas"):
            return
        canvas = self.official_tab_canvas
        hit = self._official_tab_current_hit
        width = max(canvas.winfo_width(), 500)
        measure = self._current_reference_measure()
        render_key = (
            self._hit_key(hit) if hit is not None else None,
            measure,
            round(self._official_tab_zoom, 4),
            width,
        )
        if not force and render_key == self._official_tab_last_render_key:
            return
        self._official_tab_last_render_key = render_key
        canvas.delete("all")
        self._official_tab_photo = None

        if hit is None:
            canvas.configure(scrollregion=(0, 0, width, 195))
            canvas.create_text(
                18,
                28,
                text="No official TAB reference is mapped for this arrangement/bar.",
                anchor="nw",
                fill=PALETTE.text_muted,
            )
            return

        try:
            path = resolve_reference_image(self.project, hit.page, verify_hash=True)
            with Image.open(path) as opened:
                image = opened.convert("RGB")
        except Exception as exc:
            self._official_tab_error = str(exc)
            self.official_tab_status_var.set(f"Official TAB unavailable: {exc}")
            canvas.create_text(18, 28, text=str(exc), anchor="nw", fill=PALETTE.danger)
            return

        base_scale = max((width - 24) / max(image.width, 1), 0.05)
        scale = min(max(base_scale * self._official_tab_zoom, 0.05), 4.0)
        scaled_width = max(int(image.width * scale), 1)
        scaled_height = max(int(image.height * scale), 1)
        rendered = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
        self._official_tab_photo = ImageTk.PhotoImage(rendered)
        canvas.create_image(0, 0, image=self._official_tab_photo, anchor="nw")
        canvas.configure(scrollregion=(0, 0, scaled_width, scaled_height))

        x0, y0, x1, y1 = hit.mapping.normalized_bbox
        rx0, ry0 = x0 * scaled_width, y0 * scaled_height
        rx1, ry1 = x1 * scaled_width, y1 * scaled_height
        canvas.create_rectangle(rx0 + 2, ry0 + 2, rx1 - 2, ry1 - 2, outline=PALETTE.warning, width=4)
        banner = f"Mapped bars {hit.mapping.measure_start}-{hit.mapping.measure_end}"
        if measure is not None:
            banner += f" · current bar {measure}"
        canvas.create_rectangle(rx0 + 6, ry0 + 6, min(rx0 + 310, rx1 - 6), ry0 + 30, fill=PALETTE.canvas, outline=PALETTE.warning)
        canvas.create_text(rx0 + 12, ry0 + 18, text=banner, anchor="w", fill=PALETTE.warning, font=("Segoe UI", 9, "bold"))

        if scaled_width > 0:
            canvas.xview_moveto(min(max(rx0 - 12, 0.0) / scaled_width, 1.0))
        if scaled_height > 0:
            canvas.yview_moveto(min(max(ry0 - 12, 0.0) / scaled_height, 1.0))

    def _change_official_tab_zoom(self, factor: float) -> None:
        self._official_tab_zoom = min(max(self._official_tab_zoom * factor, 0.35), 4.0)
        self._official_tab_last_render_key = None
        self._draw_official_tab_reference(force=True)

    def _fit_official_tab_width(self) -> None:
        self._official_tab_zoom = 1.0
        self._official_tab_last_render_key = None
        self._draw_official_tab_reference(force=True)

    def _official_tab_choice_changed(self, _event=None) -> None:
        hit = self._official_tab_choice_map.get(self.official_tab_choice_var.get())
        if hit is None:
            return
        self._official_tab_current_hit = hit
        self._official_tab_manual_key = self._hit_key(hit)
        self._official_tab_last_render_key = None
        try:
            self._seek_to(seek_seconds_for_measure(self._eof_measure_windows, hit.mapping.measure_start))
        except ValueError:
            self._sync_official_tab_reference(force=True)

    def _step_official_tab_reference(self, delta: int) -> None:
        hits = reference_hits_for_role(self._official_tab_manifest, self._active_reference_role())
        if not hits:
            return
        current_key = self._hit_key(self._official_tab_current_hit) if self._official_tab_current_hit else None
        index = next((i for i, item in enumerate(hits) if self._hit_key(item) == current_key), 0)
        index = min(max(index + delta, 0), len(hits) - 1)
        hit = hits[index]
        self._official_tab_current_hit = hit
        self._official_tab_manual_key = self._hit_key(hit)
        self._official_tab_last_render_key = None
        try:
            self._seek_to(seek_seconds_for_measure(self._eof_measure_windows, hit.mapping.measure_start))
        except ValueError:
            self._sync_official_tab_reference(force=True)

    def _seek_official_tab_start(self) -> None:
        hit = self._official_tab_current_hit
        if hit is None:
            return
        try:
            seconds = seek_seconds_for_measure(self._eof_measure_windows, hit.mapping.measure_start)
        except ValueError as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return
        self._seek_to(seconds)

    def _add_official_tab_page(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self,
            title="Add official TAB reference page",
            filetypes=(
                ("TAB page images", "*.jpg *.jpeg *.png"),
                ("JPEG images", "*.jpg *.jpeg"),
                ("PNG images", "*.png"),
            ),
        )
        if not filename:
            return
        current = self._current_reference_measure() or 1
        last_known = self._eof_measure_windows[-1].number if getattr(self, "_eof_measure_windows", []) else current
        suggested_last = min(current + 7, last_known)
        dialog = _ReferenceMappingDialog(
            self,
            role=self._active_reference_role(),
            first_measure=current,
            last_measure=max(suggested_last, current),
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return
        role, first, last, page_label = dialog.result
        try:
            hit = register_reference_page(
                self.project,
                Path(filename),
                arrangement=role,
                measure_start=first,
                measure_end=last,
                printed_page=page_label,
            )
            self._official_tab_manifest = load_reference_manifest(self.project, verify_files=True)
        except Exception as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return
        self._official_tab_error = None
        self._official_tab_current_hit = hit
        self._official_tab_manual_key = self._hit_key(hit)
        self._official_tab_last_render_key = None
        self._set_official_tab_visible(True, user_choice=True)
        self._sync_official_tab_reference(force=True)

    def _remove_official_tab_mapping(self) -> None:
        hit = self._official_tab_current_hit
        if hit is None:
            return
        if not messagebox.askyesno(
            "Official TAB Reference",
            (
                f"Remove {hit.label} from this project's reference manifest?\n\n"
                "The private copied image will remain on disk and no musical/arrangement data will be changed."
            ),
            parent=self,
        ):
            return
        try:
            self._official_tab_manifest = remove_reference_mapping(
                self.project,
                page_id=hit.page.page_id,
                mapping_id=hit.mapping.mapping_id,
            )
        except Exception as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return
        self._official_tab_current_hit = None
        self._official_tab_manual_key = None
        self._official_tab_last_render_key = None
        self._sync_official_tab_reference(force=True)
