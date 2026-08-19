from __future__ import annotations

import argparse
import json
from pathlib import Path

from .score_mapping_review import load_score_for_mapping_review
from .score_role_composition_fanout_review import (
    compose_and_persist_score_role_composition_fanout,
    load_current_score_role_composition_fanout,
    preview_score_role_composition_overlaps,
)
from .score_role_composition_overlap_review import ScoreRoleCompositionOverlapDecisionPlan
from .score_role_composition_review import (
    ScoreRoleCompositionPlan,
    load_current_score_role_composition,
    record_score_role_composition,
)
from .score_source import ArrangementRole

_ROLE_CHOICES = [role.value for role in ArrangementRole]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-composition",
        description=(
            "Build and review issue #232 multi-source-track-per-role composition: the "
            "persisted selection plan, cross-track overlap evidence, and the composed "
            "per-role fan-out artifact (review/score_role_composition_fanout.json)"
        ),
    )
    parser.add_argument("project", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "plan-show",
        help="Show the current persisted composition plan (which score tracks compose each role)",
    )

    plan_select = subparsers.add_parser(
        "plan-select",
        help=(
            "Set or replace one role's ordered selected source tracks, preserving every "
            "other role's current selection. The first track must be that role's current "
            "human-confirmed primary mapping."
        ),
    )
    plan_select.add_argument("role", choices=_ROLE_CHOICES)
    plan_select.add_argument(
        "track_index",
        type=int,
        nargs="+",
        help="Ordered source score track index/indices, e.g. the primary track then any additions",
    )

    overlaps = subparsers.add_parser(
        "overlaps",
        help=(
            "Import the currently selected source tracks for one role and print exact "
            "cross-track overlap evidence for human review (read-only; nothing is persisted)"
        ),
    )
    overlaps.add_argument("role", choices=_ROLE_CHOICES)

    compose = subparsers.add_parser(
        "compose",
        help=(
            "Import every currently selected source track for one role, merge them per "
            "explicit human overlap decisions, and persist the composed fan-out record"
        ),
    )
    compose.add_argument("role", choices=_ROLE_CHOICES)
    compose.add_argument(
        "--decisions",
        type=Path,
        help=(
            "Path to a JSON file with one explicit resolution per currently reported "
            "overlap from `overlaps`: either {\"decisions\": [...]} or a bare JSON list "
            "of {\"role\", \"overlap\", \"resolution\"} objects, where each \"overlap\" is "
            "copied verbatim from an `overlaps` result entry and \"resolution\" is one of "
            "keep_both, keep_left, keep_right. Omit when the role has no reported overlaps."
        ),
    )

    subparsers.add_parser(
        "compose-show",
        help="Show the current persisted composed per-role fan-out artifact, if any",
    )

    return parser


def _merged_selections(
    current: ScoreRoleCompositionPlan | None,
    *,
    role: ArrangementRole,
    track_indices: list[int],
) -> dict[ArrangementRole, list[int]]:
    selections: dict[ArrangementRole, list[int]] = {}
    if current is not None:
        for selection in current.selections:
            selections[selection.role] = list(selection.source_track_indices)
    selections[role] = list(track_indices)
    return selections


def _load_decisions(
    path: Path | None,
    *,
    score_sha256: str,
    score_format: str,
) -> ScoreRoleCompositionOverlapDecisionPlan:
    if path is None:
        return ScoreRoleCompositionOverlapDecisionPlan(
            score_sha256=score_sha256, score_format=score_format
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = payload["decisions"] if isinstance(payload, dict) else payload
    # score_sha256/score_format always come from the live registered score rather than
    # from the file, so a decisions file cannot go stale against a score change while
    # still silently appearing well-formed; the underlying compose step still fails
    # closed on any decision that does not match a currently reported overlap.
    return ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=score_sha256, score_format=score_format, decisions=decisions
    )


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "plan-show":
        plan = load_current_score_role_composition(args.project)
        print(plan.model_dump_json(indent=2) if plan is not None else "null")
        return

    if args.command == "plan-select":
        current = load_current_score_role_composition(args.project)
        selections = _merged_selections(
            current, role=ArrangementRole(args.role), track_indices=args.track_index
        )
        plan = record_score_role_composition(args.project, selections=selections)
        print(plan.model_dump_json(indent=2))
        return

    if args.command == "overlaps":
        report = preview_score_role_composition_overlaps(args.project, role=ArrangementRole(args.role))
        print(report.model_dump_json(indent=2))
        return

    if args.command == "compose":
        score = load_score_for_mapping_review(args.project)
        decisions = _load_decisions(
            args.decisions, score_sha256=score.source_sha256, score_format=score.source_format
        )
        record = compose_and_persist_score_role_composition_fanout(
            args.project, role=ArrangementRole(args.role), decisions=decisions
        )
        print(record.model_dump_json(indent=2))
        return

    layer = load_current_score_role_composition_fanout(args.project)
    print(layer.model_dump_json(indent=2) if layer is not None else "null")


if __name__ == "__main__":
    main()
