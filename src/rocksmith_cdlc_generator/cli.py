from __future__ import annotations

import argparse
import json
from pathlib import Path

from .authoring_export import export_project_bass_authoring
from .build_staging import launch_dlcbuilder, register_psarc, stage_build
from .dlcbuilder import prepare_dlcbuilder_project
from .guitarpro_import import import_project_guitarpro
from .mapping_pipeline import map_project_bass
from .midi_import import import_project_midi
from .models import ProjectManifest
from .musicxml_import import import_project_musicxml
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
    new.add_argument("--instrument", action="append", dest="instruments", choices=["bass", "lead", "rhythm"], default=None)
    new.add_argument("--projects-root", type=Path, default=Path("projects"))

    normalize = sub.add_parser("normalize", help="Create canonical working WAV")
    normalize.add_argument("project", type=Path)

    tempo = sub.add_parser("tempo", help="Analyze tempo and beat grid")
    tempo.add_argument("project", type=Path)
    tempo.add_argument("--engine", choices=["librosa", "librosa-plp"], default="librosa", help="Beat tracker implementation to use")

    separate_bass = sub.add_parser("separate-bass", help="Generate stems/bass.wav with the optional audio-separator runtime")
    separate_bass.add_argument("project", type=Path)
    separate_bass.add_argument("--model", required=True, help="audio-separator model filename chosen for bass separation")
    separate_bass.add_argument("--use-directml", action="store_true", help="Use experimental DirectML acceleration when the audio-separator DML extra is installed")

    transcribe = sub.add_parser("transcribe-bass", help="Transcribe bass note events")
    transcribe.add_argument("project", type=Path)
    transcribe.add_argument("--engine", choices=["librosa-pyin"], default="librosa-pyin")
    transcribe.add_argument("--input", type=Path, help="Optional clean bass stem. If omitted, stems/bass.wav is preferred over normalized full-mix audio.")

    import_midi = sub.add_parser("import-midi", help="Import a symbolic Bass track from a Standard MIDI File")
    import_midi.add_argument("project", type=Path)
    import_midi.add_argument("--midi", required=True, type=Path, help="MIDI file to import")
    import_midi.add_argument("--track-index", type=int, help="Explicit MIDI track index when automatic Bass selection is ambiguous")

    import_gp = sub.add_parser("import-gp", help="Import Bass tablature from Guitar Pro 3/4/5")
    import_gp.add_argument("project", type=Path)
    import_gp.add_argument("--gp", required=True, type=Path, help=".gp3, .gp4, or .gp5 file to import")
    import_gp.add_argument("--track-index", type=int, help="Explicit Guitar Pro track index when automatic Bass selection is ambiguous")

    import_xml = sub.add_parser("import-musicxml", help="Import Bass notation/tab from MusicXML or compressed MXL")
    import_xml.add_argument("project", type=Path)
    import_xml.add_argument("--musicxml", required=True, type=Path, help=".musicxml, .xml, or .mxl file to import")
    import_xml.add_argument("--part-index", type=int, help="Explicit MusicXML part index when automatic Bass selection is ambiguous")

    map_bass = sub.add_parser("map-bass", help="Map bass pitches to strings and frets")
    map_bass.add_argument("project", type=Path)
    map_bass.add_argument("--tuning", default="E Standard", help="Bass tuning: E Standard, Drop D, Eb Standard, or D Standard")
    map_bass.add_argument("--max-fret", type=int, default=24, help="Highest fret the mapper may use")

    validate = sub.add_parser("validate", help="Run the unified project validation gate and build the human review queue")
    validate.add_argument("project", type=Path)

    export = sub.add_parser("export", help="Export a validation-gated authoring package")
    export.add_argument("project", type=Path)
    export.add_argument("--target", choices=["rocksmith-xml", "eof"], default="rocksmith-xml", help="Authoring target. 'eof' currently emits the same Rocksmith 2014 XML bridge.")
    export.add_argument("--instrument", choices=["bass"], default="bass", help="Arrangement to export; Milestone 7 currently supports Bass only.")

    dlcbuilder = sub.add_parser("prepare-dlcbuilder", help="Create a DLC Builder .rs2dlc project from validated Bass authoring output")
    dlcbuilder.add_argument("project", type=Path)
    dlcbuilder.add_argument("--album", required=True, help="Album name; required because the generator will not invent metadata")
    dlcbuilder.add_argument("--year", required=True, type=int, help="Release year")
    dlcbuilder.add_argument("--cover", required=True, type=Path, help="Album artwork file to reference")
    dlcbuilder.add_argument("--preview", type=Path, help="Optional preview audio. If omitted, a 30-second 44.1 kHz WAV is generated with FFmpeg.")
    dlcbuilder.add_argument("--preview-start", type=float, default=30.0, help="Preview start time in seconds; default 30")
    dlcbuilder.add_argument("--dlc-key", help="Optional DLC key; defaults to sanitized artist + title")

    stage = sub.add_parser("stage-build", help="Verify and hash all DLC Builder inputs without touching the live Rocksmith install")
    stage.add_argument("project", type=Path)
    stage.add_argument("--dlcbuilder-project", type=Path, help="Explicit .rs2dlc path when more than one exists")

    launch = sub.add_parser("launch-dlcbuilder", help="Run build-readiness checks, then open the .rs2dlc project in DLC Builder")
    launch.add_argument("project", type=Path)
    launch.add_argument("--executable", required=True, type=Path, help="Path to DLC Builder executable")
    launch.add_argument("--dlcbuilder-project", type=Path, help="Explicit .rs2dlc path when more than one exists")

    register = sub.add_parser("register-psarc", help="Verify and stage a built PSARC outside the live Rocksmith install")
    register.add_argument("project", type=Path)
    register.add_argument("--psarc", required=True, type=Path, help="PC PSARC produced by DLC Builder")

    inspect = sub.add_parser("inspect", help="Print project manifest")
    inspect.add_argument("project", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "new":
        project = create_project(audio=args.audio, projects_root=args.projects_root, artist=args.artist, title=args.title, instruments=args.instruments or ["bass"])
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
        artifact = separate_project_bass(args.project, model=args.model, use_directml=args.use_directml)
        print(artifact.model_dump_json(indent=2))
        return
    if args.command == "transcribe-bass":
        outputs = analyze_project_bass(args.project, engine=args.engine, input_path=args.input)
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return
    if args.command == "import-midi":
        print(import_project_midi(args.project, args.midi, track_index=args.track_index))
        return
    if args.command == "import-gp":
        print(import_project_guitarpro(args.project, args.gp, track_index=args.track_index))
        return
    if args.command == "import-musicxml":
        print(import_project_musicxml(args.project, args.musicxml, part_index=args.part_index))
        return
    if args.command == "map-bass":
        outputs = map_project_bass(args.project, tuning_name=args.tuning, max_fret=args.max_fret)
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
    if args.command == "export":
        outputs = export_project_bass_authoring(args.project)
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return
    if args.command == "prepare-dlcbuilder":
        output = prepare_dlcbuilder_project(
            args.project,
            album_name=args.album,
            year=args.year,
            cover=args.cover,
            preview=args.preview,
            preview_start_seconds=args.preview_start,
            dlc_key=args.dlc_key,
        )
        print(output)
        return
    if args.command == "stage-build":
        print(stage_build(args.project, dlcbuilder_project=args.dlcbuilder_project))
        return
    if args.command == "launch-dlcbuilder":
        print(launch_dlcbuilder(args.project, executable=args.executable, dlcbuilder_project=args.dlcbuilder_project))
        return
    if args.command == "register-psarc":
        print(register_psarc(args.project, args.psarc))
        return
    if args.command == "inspect":
        manifest = ProjectManifest.load(args.project.resolve())
        print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
