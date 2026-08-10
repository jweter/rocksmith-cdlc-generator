from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mapping_pipeline import map_project_bass
from .models import ProjectManifest
from .project import create_project, normalize_project
from .stems import separate_project_bass
from .tempo_pipeline import analyze_project_tempo
from .transcription_pipeline import analyze_project_bass
from .validation import validate_project, validate_project_to_disk


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cdlc", description="Rocksmith CDLC Generator")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create a project from source audio")
    new.add_argument("--audio", required=True, type=Path)
    new.add_argument("--artist")
    new.add_argument("--title", required=True)
    new.add_argument(
        "--instrument",
        action="append",
        dest="instruments",
        choices=["bass", "lead", "rhythm"],
        default=None,
    )
    new.add_argument("--projects-root", type=Path, default=Path("projects"))

    normalize = sub.add_parser("normalize", help="Create canonical working WAV")
    normalize.add_argument("project", type=Path)

    tempo = sub.add_parser("tempo", help="Analyze tempo and beat grid")
    tempo.add_argument("project", type=Path)
    tempo.add_argument(
        "--engine",
        choices=["librosa", "librosa-plp"],
        default="librosa",
        help="Beat tracker implementation to use",
    )

    separate_bass = sub.add_parser(
        "separate-bass",
        help="Generate stems/bass.wav with the optional audio-separator runtime",
    )
    separate_bass.add_argument("project", type=Path)
    separate_bass.add_argument(
        "--model",
        required=True,
        help="audio-separator model filename chosen for bass separation",
    )
    separate_bass.add_argument(
        "--use-directml",
        action="store_true",
        help="Use experimental DirectML acceleration when the audio-separator DML extra is installed",
    )

    transcribe = sub.add_parser("transcribe-bass", help="Transcribe bass note events")
    transcribe.add_argument("project", type=Path)
    transcribe.add_argument(
        "--engine",
        choices=["librosa-pyin"],
        default="librosa-pyin",
    )
    transcribe.add_argument(
        "--input",
        type=Path,
        help="Optional clean bass stem. If omitted, stems/bass.wav is preferred over normalized full-mix audio.",
    )

    map_bass = sub.add_parser("map-bass", help="Map bass pitches to strings and frets")
    map_bass.add_argument("project", type=Path)
    map_bass.add_argument(
        "--tuning",
        default="E Standard",
        help="Bass tuning: E Standard, Drop D, Eb Standard, or D Standard",
    )
    map_bass.add_argument(
        "--max-fret",
        type=int,
        default=24,
        help="Highest fret the mapper may use",
    )

    validate = sub.add_parser(
        "validate",
        help="Run the unified project validation gate and build the human review queue",
    )
    validate.add_argument("project", type=Path)

    inspect = sub.add_parser("inspect", help="Print project manifest")
    inspect.add_argument("project", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "new":
        project = create_project(
            audio=args.audio,
            projects_root=args.projects_root,
            artist=args.artist,
            title=args.title,
            instruments=args.instruments or ["bass"],
        )
        print(project)
        return

    if args.command == "normalize":
        print(normalize_project(args.project))
        return

    if args.command == "tempo":
        outputs = analyze_project_tempo(args.project, engine=args.engine)
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return

    if args.command == "separate-bass":
        artifact = separate_project_bass(
            args.project,
            model=args.model,
            use_directml=args.use_directml,
        )
        print(artifact.model_dump_json(indent=2))
        return

    if args.command == "transcribe-bass":
        outputs = analyze_project_bass(
            args.project,
            engine=args.engine,
            input_path=args.input,
        )
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return

    if args.command == "map-bass":
        outputs = map_project_bass(
            args.project,
            tuning_name=args.tuning,
            max_fret=args.max_fret,
        )
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return

    if args.command == "validate":
        report = validate_project(args.project)
        output = validate_project_to_disk(args.project)
        print(report.model_dump_json(indent=2))
        print(f"Validation report: {output}")
        if not report.can_package:
            raise SystemExit(2)
        return

    if args.command == "inspect":
        manifest = ProjectManifest.load(args.project.resolve())
        print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
