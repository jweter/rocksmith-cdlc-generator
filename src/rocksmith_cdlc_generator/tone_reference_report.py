from __future__ import annotations

import re
from pathlib import Path

from .tone_reference_recommendations import ToneRecommendationEvidenceReport


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "tone-evidence"


def render_tone_reference_markdown(report: ToneRecommendationEvidenceReport) -> str:
    """Render reviewer-facing evidence without changing or approving a tone plan."""
    lines = [
        f"# Local Tone Reference Evidence: {report.artist} — {report.title}",
        "",
        "> Evidence only. Human review is required. This report cannot apply settings or approve injection.",
        "",
        "## Provenance",
        "",
        f"- Bound plan SHA-256: `{report.bound_plan_sha256}`",
        f"- Private library scan root: `{report.library_scan_root}`",
        f"- Indexed PSARCs: {report.library_psarc_count}",
        f"- Indexed tones: {report.library_tone_count}",
        f"- Human review required: **{'yes' if report.human_review_required else 'no'}**",
        f"- Automatic apply permitted: **{'yes' if report.can_auto_apply else 'no'}**",
        "",
    ]

    for arrangement in report.arrangements:
        lines.extend([
            f"## {arrangement.label} ({arrangement.arrangement})",
            "",
            "Resolved query device keys: " + (
                ", ".join(f"`{key}`" for key in arrangement.query_device_keys)
                if arrangement.query_device_keys else "none"
            ),
            "",
        ])
        for warning in arrangement.warnings:
            lines.append(f"- ⚠ {warning}")
        if arrangement.warnings:
            lines.append("")

        if not arrangement.candidates:
            lines.extend(["No eligible local references were surfaced.", ""])
            continue

        for index, candidate in enumerate(arrangement.candidates, start=1):
            source_label = " — ".join(
                item for item in [candidate.artist, candidate.title, candidate.tone_name or candidate.tone_key] if item
            )
            lines.extend([
                f"### Candidate {index}: {source_label}",
                "",
                f"- Score: {candidate.score:.4f}",
                f"- Source authority: `{candidate.source_type}` ({candidate.authority_weight:.2f})",
                f"- Source PSARC SHA-256: `{candidate.source_psarc_sha256}`",
                f"- Source path: `{candidate.source_path}`",
                f"- Tone fingerprint: `{candidate.fingerprint}`",
                "- Matched device keys: " + ", ".join(f"`{key}`" for key in candidate.matched_device_keys),
                "- Descriptors: " + (", ".join(candidate.descriptors) if candidate.descriptors else "none"),
                "- Evidence only: **yes**",
                "",
                "Components:",
                "",
            ])
            for component in candidate.components:
                identity = component.device_name or component.device_key
                details = [component.slot, identity, component.device_type, component.category]
                lines.append("- " + " | ".join(item for item in details if item))
                if component.knob_values:
                    knob_text = ", ".join(
                        f"{key}={value:g}" for key, value in sorted(component.knob_values.items())
                    )
                    lines.append(f"  - Knobs: {knob_text}")
            lines.append("")

    lines.extend([
        "## Review boundary",
        "",
        "This artifact is descriptive evidence only. Selecting a candidate here does not mutate the bound tone plan, copy knob values, approve a component, or mark a tone safe for injection.",
        "",
    ])
    return "\n".join(lines)


def write_tone_reference_report_bundle(
    report: ToneRecommendationEvidenceReport,
    output_dir: Path,
    *,
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Write machine-readable JSON and reviewer-readable Markdown side by side."""
    output_dir.mkdir(parents=True, exist_ok=True)
    name = stem or f"{_slug(report.artist)}-{_slug(report.title)}-tone-reference-evidence"
    json_path = output_dir / f"{name}.json"
    markdown_path = output_dir / f"{name}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_tone_reference_markdown(report), encoding="utf-8")
    return json_path, markdown_path
