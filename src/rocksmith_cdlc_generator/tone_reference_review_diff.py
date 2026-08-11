from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from .tone_review import ToneReviewArtifact, ToneComponentReview, ToneReviewItem


class KnobValueChange(BaseModel):
    name: str
    original: float | None = None
    staged: float | None = None


class ComponentSettingsDiff(BaseModel):
    arrangement: str
    arrangement_label: str
    family: str
    slot: str | None = None
    original_device_key: str | None = None
    staged_device_key: str | None = None
    original_device_name: str | None = None
    staged_device_name: str | None = None
    knob_changes: list[KnobValueChange] = Field(default_factory=list)


class ToneReviewSettingsDiff(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    catalog_sha256: str
    changes: list[ComponentSettingsDiff] = Field(default_factory=list)
    unchanged_component_count: int = Field(ge=0)
    human_review_required: bool = True
    can_approve: bool = False
    can_inject: bool = False


def _component_key(component: ToneComponentReview) -> tuple[str, str]:
    return ((component.slot or "").casefold(), component.family.casefold())


def _components_by_key(tone: ToneReviewItem) -> dict[tuple[str, str], ToneComponentReview]:
    result: dict[tuple[str, str], ToneComponentReview] = {}
    for component in tone.components:
        key = _component_key(component)
        if key in result:
            raise ValueError(
                f"tone review contains duplicate component identity in arrangement {tone.arrangement!r}: "
                f"slot={component.slot!r}, family={component.family!r}"
            )
        result[key] = component
    return result


def _tones_by_arrangement(artifact: ToneReviewArtifact) -> dict[str, ToneReviewItem]:
    result: dict[str, ToneReviewItem] = {}
    for tone in artifact.tones:
        if tone.arrangement in result:
            raise ValueError(f"tone review contains duplicate arrangement {tone.arrangement!r}")
        result[tone.arrangement] = tone
    return result


def build_staged_settings_diff(
    original: ToneReviewArtifact,
    staged: ToneReviewArtifact,
) -> ToneReviewSettingsDiff:
    """Compare an original pending review with a staged pending review.

    This is a descriptive reviewer aid only. It cannot approve components, approve
    tones, mutate either artifact, or mark anything injection-ready.
    """
    if original.artist != staged.artist or original.title != staged.title:
        raise ValueError("original and staged tone reviews identify different songs")
    if original.catalog_sha256 != staged.catalog_sha256:
        raise ValueError("original and staged tone reviews use different tone catalogs")
    if original.bound_plan_sha256 != staged.bound_plan_sha256:
        raise ValueError("original and staged tone reviews were created from different bound plans")
    if original.ready_for_injection or staged.ready_for_injection:
        raise ValueError("settings diff is only valid before the injection-ready gate closes")

    original_tones = _tones_by_arrangement(original)
    staged_tones = _tones_by_arrangement(staged)
    if set(original_tones) != set(staged_tones):
        raise ValueError("original and staged tone reviews must contain the same arrangements")

    changes: list[ComponentSettingsDiff] = []
    unchanged = 0
    for arrangement in sorted(original_tones, key=str.casefold):
        before_tone = original_tones[arrangement]
        after_tone = staged_tones[arrangement]
        if before_tone.label != after_tone.label:
            raise ValueError(f"arrangement label changed for {arrangement!r}")

        before_components = _components_by_key(before_tone)
        after_components = _components_by_key(after_tone)
        if set(before_components) != set(after_components):
            raise ValueError(
                f"original and staged tone reviews must contain the same components for {arrangement!r}"
            )

        for key in sorted(before_components):
            before = before_components[key]
            after = after_components[key]
            knob_changes = [
                KnobValueChange(
                    name=name,
                    original=before.knob_values.get(name),
                    staged=after.knob_values.get(name),
                )
                for name in sorted(set(before.knob_values) | set(after.knob_values), key=str.casefold)
                if before.knob_values.get(name) != after.knob_values.get(name)
            ]
            changed = (
                before.device_key != after.device_key
                or before.device_name != after.device_name
                or bool(knob_changes)
            )
            if not changed:
                unchanged += 1
                continue
            changes.append(
                ComponentSettingsDiff(
                    arrangement=arrangement,
                    arrangement_label=before_tone.label,
                    family=before.family,
                    slot=before.slot,
                    original_device_key=before.device_key,
                    staged_device_key=after.device_key,
                    original_device_name=before.device_name,
                    staged_device_name=after.device_name,
                    knob_changes=knob_changes,
                )
            )

    return ToneReviewSettingsDiff(
        artist=original.artist,
        title=original.title,
        bound_plan_sha256=original.bound_plan_sha256,
        catalog_sha256=original.catalog_sha256,
        changes=changes,
        unchanged_component_count=unchanged,
        human_review_required=True,
        can_approve=False,
        can_inject=False,
    )


def render_staged_settings_diff_markdown(report: ToneReviewSettingsDiff) -> str:
    lines = [
        f"# Staged Tone Settings Diff: {report.artist} — {report.title}",
        "",
        "> Review aid only. Human approval remains separate; this artifact cannot approve or inject tone settings.",
        "",
        "## Provenance",
        "",
        f"- Bound plan SHA-256: `{report.bound_plan_sha256}`",
        f"- Tone catalog SHA-256: `{report.catalog_sha256}`",
        f"- Changed components: {len(report.changes)}",
        f"- Unchanged components: {report.unchanged_component_count}",
        "",
    ]
    if not report.changes:
        lines.extend(["No staged setting changes were detected.", ""])
    for change in report.changes:
        identity = change.slot or change.family
        lines.extend([
            f"## {change.arrangement_label} / {identity}",
            "",
            f"- Family: `{change.family}`",
            f"- Original device: `{change.original_device_key or 'unresolved'}`"
            + (f" ({change.original_device_name})" if change.original_device_name else ""),
            f"- Staged device: `{change.staged_device_key or 'unresolved'}`"
            + (f" ({change.staged_device_name})" if change.staged_device_name else ""),
        ])
        if change.knob_changes:
            lines.extend(["- Knob changes:", ""])
            for knob in change.knob_changes:
                before = "unset" if knob.original is None else f"{knob.original:g}"
                after = "unset" if knob.staged is None else f"{knob.staged:g}"
                lines.append(f"  - `{knob.name}`: {before} → {after}")
        lines.append("")
    lines.extend([
        "## Review boundary",
        "",
        "This comparison does not modify either review artifact, does not approve any component or tone, and does not close the injection gate.",
        "",
    ])
    return "\n".join(lines)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "tone-review-diff"


def write_staged_settings_diff_bundle(
    report: ToneReviewSettingsDiff,
    output_dir: Path,
    *,
    stem: str | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = stem or f"{_slug(report.artist)}-{_slug(report.title)}-staged-tone-diff"
    json_path = output_dir / f"{name}.json"
    markdown_path = output_dir / f"{name}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_staged_settings_diff_markdown(report), encoding="utf-8")
    return json_path, markdown_path
