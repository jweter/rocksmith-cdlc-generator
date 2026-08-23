from __future__ import annotations

import json
import os
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .design_tokens import TYPOGRAPHY
from .desktop_runner import desktop_command_runner
from .desktop_theme import status_dark_foreground
from .models import ProjectManifest
from .multi_arrangement_plan import build_multi_arrangement_workflow_plan
from .project import create_project
from .project_score import register_project_score
from .score_mapping_review import confirm_score_mapping
from .score_mapping_status_presentation import MappingRoleStatusPresentation, present_mapping_role_status
from .score_source import ArrangementRole, ProjectScoreSource
from .source_intake import SourceRightsClass
from .source_rights_review import latest_source_rights_reviews, record_source_rights_review
from .workflow_runner import run_automatic_first_draft


APP_TITLE = "Rocksmith CDLC Generator"
_SUPPORTED_AUDIO = [("Audio files", "*.wav *.flac *.mp3 *.m4a *.ogg *.aac *.wma"), ("All files", "*.*")]
_SUPPORTED_SCORES = [
    ("Supported scores", "*.gp3 *.gp4 *.gp5 *.musicxml *.xml *.mxl"),
    ("All files", "*.*"),
]
_RIGHTS_CHOICES = [
    SourceRightsClass.user_owned_local.value,
    SourceRightsClass.licensed_download.value,
    SourceRightsClass.creative_commons.value,
    SourceRightsClass.public_domain.value,
    SourceRightsClass.self_recorded.value,
]
_MAPPING_SUFFIXES = (" ✓ confirmed", " • review required")


def _settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".rocksmith-cdlc-generator"))
    return base / "RocksmithCDLCGenerator" / "desktop.json"


def _load_recent_projects() -> list[str]:
    path = _settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    values = data.get("recent_projects", []) if isinstance(data, dict) else []
    return [str(value) for value in values if isinstance(value, str)][:10]


def _save_recent_projects(projects: list[str]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"recent_projects": projects[:10]}, indent=2), encoding="utf-8")


def _bare_mapping_label(value: str) -> str:
    for suffix in _MAPPING_SUFFIXES:
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _mapping_refresh_value(
    *,
    current_value: str,
    labels: list[str],
    mapped_track_index: int | None,
    human_confirmed: bool = False,
) -> str:
    """Render persisted mapping authority without erasing a valid pending UI selection."""

    if mapped_track_index is not None:
        match = next(
            (label for label in labels if label.startswith(f"{mapped_track_index}:")),
            "",
        )
        if not match:
            return ""
        suffix = " ✓ confirmed" if human_confirmed else " • review required"
        return match + suffix

    pending = _bare_mapping_label(current_value)
    return pending if pending in labels else ""


class DesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x760")
        self.minsize(900, 620)

        self.project: Path | None = None
        self.recent_projects = _load_recent_projects()
        self._busy = False

        self.project_var = tk.StringVar(value="No project open")
        self.song_var = tk.StringVar(value="Choose New Project or Open Project to begin.")
        self.next_action_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.score_var = tk.StringVar(value="No complete score registered")
        self.rights_note_var = tk.StringVar(value="")
        self.rights_source_var = tk.StringVar(value="")
        self.rights_class_var = tk.StringVar(value=_RIGHTS_CHOICES[0])
        self.mapping_vars = {
            ArrangementRole.bass: tk.StringVar(),
            ArrangementRole.lead: tk.StringVar(),
            ArrangementRole.rhythm: tk.StringVar(),
        }
        _initial_mapping_status = present_mapping_role_status(
            has_score=False, has_selection=False, human_confirmed=False
        ).text
        self.mapping_status_vars = {
            ArrangementRole.bass: tk.StringVar(value=_initial_mapping_status),
            ArrangementRole.lead: tk.StringVar(value=_initial_mapping_status),
            ArrangementRole.rhythm: tk.StringVar(value=_initial_mapping_status),
        }

        self._build_menu()
        self._build_layout()
        self._refresh_recent_menu()

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Project…", command=self.new_project_dialog)
        file_menu.add_command(label="Open Project…", command=self.open_project_dialog)
        self.recent_menu = tk.Menu(file_menu, tearoff=False)
        file_menu.add_cascade(label="Recent Projects", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Open Project Folder", command=self.open_project_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        project_menu = tk.Menu(menu, tearoff=False)
        project_menu.add_command(label="Register Complete Score…", command=self.register_score_dialog)
        project_menu.add_command(label="Run Safe Automatic Steps", command=self.run_automatic_steps)
        project_menu.add_command(label="Refresh", command=self.refresh_project)
        menu.add_cascade(label="Project", menu=project_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.song_var, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(top, textvariable=self.project_var).grid(row=2, column=0, sticky="w", pady=(2, 0))
        buttons = ttk.Frame(top)
        buttons.grid(row=0, column=1, rowspan=3, sticky="e")
        ttk.Button(buttons, text="New Project", command=self.new_project_dialog).pack(side="left", padx=4)
        ttk.Button(buttons, text="Open Project", command=self.open_project_dialog).pack(side="left", padx=4)
        self.run_button = ttk.Button(buttons, text="Run Next Steps", command=self.run_automatic_steps)
        self.run_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh_project).pack(side="left", padx=4)
        top.columnconfigure(0, weight=1)

        # Kept as an addressable attribute (not a local var) so a subclass that
        # replaces this raw plan-step callout with a friendlier guided
        # presentation -- see GuidedDesktopApp, which duplicates this exact
        # information in its "Song progress" panel -- can hide the redundant
        # copy instead of leaving a second, blank-until-refresh box stacked
        # directly beneath it (#305).
        self.next_action_callout = ttk.LabelFrame(self, text="Next action", padding=10)
        self.next_action_callout.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(self.next_action_callout, textvariable=self.next_action_var, wraplength=1050).pack(anchor="w")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.workflow_tab = ttk.Frame(notebook, padding=10)
        self.score_tab = ttk.Frame(notebook, padding=10)
        self.rights_tab = ttk.Frame(notebook, padding=10)
        self.log_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.workflow_tab, text="Workflow")
        notebook.add(self.score_tab, text="Score & Mappings")
        notebook.add(self.rights_tab, text="Rights / Provenance")
        notebook.add(self.log_tab, text="Activity Log")

        self.workflow_tree = ttk.Treeview(
            self.workflow_tab,
            columns=("status", "mode", "reason"),
            show="headings",
            selectmode="browse",
        )
        self.workflow_tree.heading("status", text="Status")
        self.workflow_tree.heading("mode", text="Mode")
        self.workflow_tree.heading("reason", text="Step / reason")
        self.workflow_tree.column("status", width=90, anchor="center")
        self.workflow_tree.column("mode", width=90, anchor="center")
        self.workflow_tree.column("reason", width=780, anchor="w")
        self.workflow_tree.pack(fill="both", expand=True)

        score_header = ttk.Frame(self.score_tab)
        score_header.pack(fill="x")
        ttk.Label(score_header, textvariable=self.score_var, font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(score_header, text="Register / Replace Score", command=self.register_score_dialog).pack(side="right")

        # The human-confirmation mapping controls are the actual score-arrangements gate action, so
        # they are built directly under the header rather than below the track inventory. On a
        # constrained window/notebook height (shell chrome above the notebook can leave this tab very
        # short) a control placed after a tall fixed-height track table can be clipped with no scroll
        # path, making the project unable to advance. See Product Reality issue #304.
        mapping_box = ttk.LabelFrame(self.score_tab, text="Human-confirmed Rocksmith arrangement mappings", padding=10)
        mapping_box.pack(fill="x", pady=(10, 12))
        self.mapping_combos: dict[ArrangementRole, ttk.Combobox] = {}
        self.mapping_status_labels: dict[ArrangementRole, ttk.Label] = {}
        for row, role in enumerate((ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm)):
            ttk.Label(mapping_box, text=role.value.title(), width=10).grid(row=row, column=0, sticky="w", pady=4)
            combo = ttk.Combobox(mapping_box, textvariable=self.mapping_vars[role], state="readonly", width=68)
            combo.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=4)
            self.mapping_combos[role] = combo
            ttk.Button(
                mapping_box,
                text="Confirm",
                command=lambda selected_role=role: self.confirm_mapping(selected_role),
            ).grid(row=row, column=2, pady=4)
            # #305: a dedicated semantic-status label (color + symbol + label text, never
            # color-alone) beside each role's control, instead of the confirmation state
            # being legible only from suffix text inside the editable combobox value. See
            # score_mapping_status_presentation.present_mapping_role_status.
            status_label = ttk.Label(
                mapping_box, textvariable=self.mapping_status_vars[role], font=TYPOGRAPHY["body"].as_tuple()
            )
            status_label.grid(row=row, column=3, sticky="w", padx=(8, 0), pady=4)
            self.mapping_status_labels[role] = status_label
        mapping_box.columnconfigure(1, weight=1)
        ttk.Label(
            mapping_box,
            text="Mappings are never auto-accepted. Confidence and track names are review aids only.",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        track_frame = ttk.Frame(self.score_tab)
        track_frame.pack(fill="both", expand=True)
        self.track_tree = ttk.Treeview(
            track_frame,
            columns=("index", "name", "hint", "notes"),
            show="headings",
            height=8,
        )
        for key, title, width in (
            ("index", "Track", 65),
            ("name", "Name", 260),
            ("hint", "Instrument hint", 220),
            ("notes", "Notes", 90),
        ):
            self.track_tree.heading(key, text=title)
            self.track_tree.column(key, width=width, anchor="w")
        # The track inventory is reference information, not a control the user must reach to confirm
        # a mapping, but it still gets its own scrollbar so every track row stays reachable even when
        # the tab has little vertical room left.
        track_scroll = ttk.Scrollbar(track_frame, orient="vertical", command=self.track_tree.yview)
        self.track_tree.configure(yscrollcommand=track_scroll.set)
        self.track_tree.pack(side="left", fill="both", expand=True)
        track_scroll.pack(side="right", fill="y")

        rights_intro = ttk.Label(
            self.rights_tab,
            text=(
                "Confirm only local files you are permitted to use. This review records provenance for local processing; "
                "it does not grant redistribution rights."
            ),
            wraplength=1000,
        )
        rights_intro.pack(anchor="w", pady=(0, 10))
        rights_form = ttk.Frame(self.rights_tab)
        rights_form.pack(fill="x")
        ttk.Label(rights_form, text="Source").grid(row=0, column=0, sticky="w", pady=4)
        self.rights_source_combo = ttk.Combobox(
            rights_form, textvariable=self.rights_source_var, state="readonly", width=84
        )
        self.rights_source_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(rights_form, text="Classification").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            rights_form,
            textvariable=self.rights_class_var,
            values=_RIGHTS_CHOICES,
            state="readonly",
            width=30,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(rights_form, text="Note").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(rights_form, textvariable=self.rights_note_var).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(rights_form, text="Record Human Review", command=self.record_rights_review).grid(
            row=3, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        rights_form.columnconfigure(1, weight=1)
        self.rights_status = tk.Text(self.rights_tab, height=12, wrap="word", state="disabled")
        self.rights_status.pack(fill="both", expand=True, pady=(14, 0))

        self.log_text = tk.Text(self.log_tab, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        status = ttk.Frame(self, padding=(12, 4, 12, 10))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var).pack(side="left")

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        valid = [path for path in self.recent_projects if (Path(path) / "project.json").is_file()]
        self.recent_projects = valid
        if not valid:
            self.recent_menu.add_command(label="(none)", state="disabled")
            return
        for path in valid:
            self.recent_menu.add_command(label=path, command=lambda p=path: self.load_project(Path(p)))

    def _remember_project(self, project: Path) -> None:
        value = str(project)
        self.recent_projects = [value, *[item for item in self.recent_projects if item != value]][:10]
        _save_recent_projects(self.recent_projects)
        self._refresh_recent_menu()

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        self.run_button.configure(state="disabled" if busy else "normal")
        if message:
            self.status_var.set(message)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _run_background(self, label: str, operation, on_success=None) -> None:
        if self._busy:
            return
        self._set_busy(True, label)
        self._log(label)

        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:  # GUI boundary: surface useful failure without crashing the app.
                details = traceback.format_exc()
                self.after(0, lambda: self._background_failed(exc, details))
                return
            self.after(0, lambda: self._background_succeeded(result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _background_failed(self, exc: Exception, details: str) -> None:
        self._set_busy(False, f"Failed: {exc}")
        self._log(details)
        messagebox.showerror(APP_TITLE, str(exc))
        self.refresh_project()

    def _background_succeeded(self, result, on_success) -> None:
        self._set_busy(False, "Ready")
        if on_success is not None:
            on_success(result)
        self.refresh_project()

    def new_project_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("New CDLC Project")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        artist = tk.StringVar()
        title = tk.StringVar()
        audio = tk.StringVar()
        score = tk.StringVar()
        root = tk.StringVar(value=str(Path.home() / "Documents" / "Rocksmith CDLC Projects"))

        def choose_audio() -> None:
            selected = filedialog.askopenfilename(parent=dialog, filetypes=_SUPPORTED_AUDIO)
            if selected:
                audio.set(selected)
                if not title.get():
                    title.set(Path(selected).stem)

        def choose_score() -> None:
            selected = filedialog.askopenfilename(parent=dialog, filetypes=_SUPPORTED_SCORES)
            if selected:
                score.set(selected)

        def choose_root() -> None:
            selected = filedialog.askdirectory(parent=dialog, initialdir=root.get() or None)
            if selected:
                root.set(selected)

        rows = [
            ("Artist", artist, None),
            ("Title", title, None),
            ("Song audio", audio, choose_audio),
            ("Complete score", score, choose_score),
            ("Projects folder", root, choose_root),
        ]
        for row, (label, variable, chooser) in enumerate(rows):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
            ttk.Entry(dialog, textvariable=variable, width=62).grid(row=row, column=1, sticky="ew", padx=6, pady=6)
            if chooser:
                ttk.Button(dialog, text="Browse…", command=chooser).grid(row=row, column=2, padx=10, pady=6)

        ttk.Label(
            dialog,
            text="New desktop projects enable Bass, Lead, and Rhythm by default. Human review gates remain active.",
            wraplength=650,
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 4))

        def create() -> None:
            if not title.get().strip() or not audio.get().strip() or not root.get().strip():
                messagebox.showwarning(APP_TITLE, "Title, song audio, and projects folder are required.", parent=dialog)
                return
            dialog.destroy()

            def operation() -> Path:
                project = create_project(
                    audio=Path(audio.get()),
                    projects_root=Path(root.get()),
                    artist=artist.get().strip() or None,
                    title=title.get().strip(),
                    instruments=["bass", "lead", "rhythm"],
                )
                if score.get().strip():
                    register_project_score(project, Path(score.get()))
                return project

            self._run_background("Creating project…", operation, self.load_project)

        actions = ttk.Frame(dialog)
        actions.grid(row=6, column=0, columnspan=3, sticky="e", padx=10, pady=10)
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right", padx=4)
        ttk.Button(actions, text="Create Project", command=create).pack(side="right", padx=4)

    def open_project_dialog(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Open CDLC Project")
        if selected:
            self.load_project(Path(selected))

    def load_project(self, project: Path) -> None:
        project = project.expanduser().resolve()
        try:
            manifest = ProjectManifest.load(project)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open project:\n{exc}")
            return
        self.project = project
        self.project_var.set(str(project))
        self.song_var.set(manifest.project_name)
        self._remember_project(project)
        self._log(f"Opened project: {project}")
        self.refresh_project()

    def open_project_folder(self) -> None:
        if self.project is None:
            return
        if os.name == "nt":
            os.startfile(self.project)  # type: ignore[attr-defined]
        else:
            self._log(f"Project folder: {self.project}")

    def register_score_dialog(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return
        selected = filedialog.askopenfilename(parent=self, filetypes=_SUPPORTED_SCORES)
        if not selected:
            return
        self._run_background(
            "Registering complete score…",
            lambda: register_project_score(self.project, Path(selected)),
        )

    def refresh_project(self) -> None:
        if self.project is None or not (self.project / "project.json").is_file():
            return
        try:
            manifest = ProjectManifest.load(self.project)
            plan = build_multi_arrangement_workflow_plan(self.project)
        except Exception as exc:
            self.status_var.set(f"Refresh failed: {exc}")
            self._log(traceback.format_exc())
            return

        self.song_var.set(manifest.project_name)
        self.workflow_tree.delete(*self.workflow_tree.get_children())
        for step in plan.steps:
            summary = f"{step.title} — {step.reason}"
            self.workflow_tree.insert("", "end", values=(step.status, step.mode, summary))
        next_step = next((step for step in plan.steps if step.step_id == plan.next_step_id), None)
        if next_step is None:
            self.next_action_var.set("Workflow has no remaining blocking or ready step.")
        else:
            self.next_action_var.set(f"{next_step.title}: {next_step.reason}")
        self.status_var.set(
            f"Automatic steps ready: {plan.automatic_ready_steps}   •   Human gates: {plan.human_blocking_steps}"
        )
        self._refresh_score()
        self._refresh_rights()

    def _refresh_score(self) -> None:
        assert self.project is not None
        contract = self.project / "sources" / "score" / "source.json"
        self.track_tree.delete(*self.track_tree.get_children())
        if not contract.is_file():
            self.score_var.set("No complete score registered")
            for role, combo in self.mapping_combos.items():
                combo.configure(values=[])
                self._set_mapping_status(
                    role,
                    present_mapping_role_status(has_score=False, has_selection=False, human_confirmed=False),
                )
            return
        try:
            score = ProjectScoreSource.read_json(contract)
        except Exception as exc:
            self.score_var.set(f"Score contract error: {exc}")
            return
        self.score_var.set(f"{score.source_filename}   •   {score.source_format.upper()}   •   {len(score.tracks)} tracks")
        labels: list[str] = []
        for track in score.tracks:
            label = f"{track.source_track_index}: {track.name or '(unnamed)'} — {track.instrument_hint or 'unknown'} — {track.note_count} notes"
            labels.append(label)
            self.track_tree.insert(
                "",
                "end",
                values=(track.source_track_index, track.name or "", track.instrument_hint or "", track.note_count),
            )
        for role, combo in self.mapping_combos.items():
            combo.configure(values=labels)
            mapping = score.mapping_for(role)
            human_confirmed = mapping.human_confirmed if mapping is not None else False
            self.mapping_vars[role].set(
                _mapping_refresh_value(
                    current_value=self.mapping_vars[role].get(),
                    labels=labels,
                    mapped_track_index=(mapping.source_track_index if mapping is not None else None),
                    human_confirmed=human_confirmed,
                )
            )
            has_selection = bool(_bare_mapping_label(self.mapping_vars[role].get()))
            self._set_mapping_status(
                role,
                present_mapping_role_status(
                    has_score=True, has_selection=has_selection, human_confirmed=human_confirmed
                ),
            )

    def _set_mapping_status(self, role: ArrangementRole, presentation: MappingRoleStatusPresentation) -> None:
        self.mapping_status_vars[role].set(presentation.text)
        self.mapping_status_labels[role].configure(foreground=status_dark_foreground(presentation.status_state))

    def confirm_mapping(self, role: ArrangementRole) -> None:
        if self.project is None:
            return
        value = _bare_mapping_label(self.mapping_vars[role].get())
        if not value or ":" not in value:
            messagebox.showwarning(APP_TITLE, f"Choose a score track for {role.value.title()} first.")
            return
        try:
            track_index = int(value.split(":", 1)[0])
            confirm_score_mapping(self.project, role=role, source_track_index=track_index)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self._log(f"Human-confirmed {role.value} mapping to score track {track_index}.")
        self.refresh_project()

    def _source_choices(self) -> dict[str, str]:
        assert self.project is not None
        choices: dict[str, str] = {}
        manifest = ProjectManifest.load(self.project)
        choices[f"Recording audio — {manifest.source_sha256[:12]}…"] = manifest.source_sha256
        contract = self.project / "sources" / "score" / "source.json"
        if contract.is_file():
            score = ProjectScoreSource.read_json(contract)
            choices[f"Complete score — {score.source_sha256[:12]}…"] = score.source_sha256
        return choices

    def _refresh_rights(self) -> None:
        assert self.project is not None
        try:
            choices = self._source_choices()
            reviews = latest_source_rights_reviews(self.project)
        except Exception as exc:
            self._set_rights_text(f"Could not load rights state: {exc}")
            return
        labels = list(choices)
        self.rights_source_combo.configure(values=labels)
        if labels and self.rights_source_var.get() not in choices:
            self.rights_source_var.set(labels[0])
        lines = []
        for label, sha in choices.items():
            review = reviews.get(sha)
            if review is None:
                lines.append(f"REVIEW NEEDED  {label}")
            else:
                lines.append(f"REVIEWED       {label}  →  {review[1].rights_class.value}")
        self._set_rights_text("\n".join(lines) if lines else "No local project sources found.")

    def _set_rights_text(self, text: str) -> None:
        self.rights_status.configure(state="normal")
        self.rights_status.delete("1.0", "end")
        self.rights_status.insert("1.0", text)
        self.rights_status.configure(state="disabled")

    def record_rights_review(self) -> None:
        if self.project is None:
            return
        choices = self._source_choices()
        selected = self.rights_source_var.get()
        sha = choices.get(selected)
        if sha is None:
            messagebox.showwarning(APP_TITLE, "Choose a project source to review.")
            return
        try:
            output = record_source_rights_review(
                self.project,
                source_sha256=sha,
                rights_class=SourceRightsClass(self.rights_class_var.get()),
                note=self.rights_note_var.get().strip() or None,
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.rights_note_var.set("")
        self._log(f"Recorded source-rights review: {output}")
        self.refresh_project()

    def run_automatic_steps(self) -> None:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "Open or create a project first.")
            return

        def operation():
            return run_automatic_first_draft(
                self.project,
                max_steps=32,
                command_runner=desktop_command_runner,
            )

        def finished(result) -> None:
            for step in result.executed_steps:
                self._log(f"{step.step_id}: {step.command} → {step.return_code}")
            self._log(f"Automatic run stopped: {result.stop_reason}; next={result.next_step_id}")
            if result.stop_reason == "human_gate":
                self.status_var.set("Automatic work paused at a human review gate.")
            elif result.stop_reason == "complete":
                self.status_var.set("Automatic first-draft workflow complete.")

        self._run_background("Running safe automatic workflow steps…", operation, finished)


def main() -> None:
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
