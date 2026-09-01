from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from pydantic import BaseModel, ConfigDict

from .private_score_bundle import PrivateScoreBundleSpec


class PrintedScoreProjectRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec_path: Path
    source_dir: Path
    projects_root: Path
    movement_id: str


def ask_printed_score_project_request(
    parent: tk.Misc,
    *,
    initial_manifest_dir: Path | None = None,
) -> PrintedScoreProjectRequest | None:
    """Collect the four inputs needed to bootstrap a score-only project.

    No files are copied here; callers can run the actual project creation through the
    desktop background worker so hashing and private image registration never freeze
    the UI.
    """

    manifest = filedialog.askopenfilename(
        parent=parent,
        title="Choose printed-score metadata manifest",
        initialdir=str(initial_manifest_dir) if initial_manifest_dir else None,
        filetypes=(("YAML manifest", "*.yaml *.yml"), ("All files", "*.*")),
    )
    if not manifest:
        return None
    spec_path = Path(manifest).expanduser().resolve()
    try:
        spec = PrivateScoreBundleSpec.read_yaml(spec_path)
    except Exception as exc:
        messagebox.showerror(
            "Printed Score Project",
            f"Could not read that score manifest:\n{exc}",
            parent=parent,
        )
        return None

    source_dir = filedialog.askdirectory(
        parent=parent,
        title=(
            "Choose the folder containing the private score photos "
            "(" + ", ".join(page.source_filename for page in spec.pages[:3]) + "…)"
        ),
    )
    if not source_dir:
        return None

    projects_root = filedialog.askdirectory(
        parent=parent,
        title="Choose where the new Rocksmith project folder should be created",
    )
    if not projects_root:
        return None

    options = "\n".join(
        f"  {movement.movement_id} — {movement.title} (pages {movement.start_page}-{movement.end_page})"
        for movement in spec.movements
    )
    default = spec.movements[0].movement_id
    while True:
        movement_id = simpledialog.askstring(
            "Printed Score Project",
            "Choose the movement/section for this practice project:\n\n"
            + options
            + f"\n\nMovement ID (default: {default}):",
            parent=parent,
            initialvalue=default,
        )
        if movement_id is None:
            return None
        movement_id = movement_id.strip()
        if any(movement.movement_id == movement_id for movement in spec.movements):
            break
        messagebox.showwarning(
            "Printed Score Project",
            f"{movement_id!r} is not a movement ID in this manifest.",
            parent=parent,
        )

    return PrintedScoreProjectRequest(
        spec_path=spec_path,
        source_dir=Path(source_dir).expanduser().resolve(),
        projects_root=Path(projects_root).expanduser().resolve(),
        movement_id=movement_id,
    )
