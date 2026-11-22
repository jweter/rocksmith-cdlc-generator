"""Fail-closed published model-card comparison; NEVER a model execution gate.

No network, model loading, artifact download, file mutation or runtime
permissions. Sizes are publisher-specific weights, NOT measured host RAM.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

HERE = Path(__file__).resolve().parents[2]
CATALOG_PATH = HERE / "engineering" / "bass-separator-model-candidates.json"
MODEL_ID = re.compile(r"^[a-z][a-z0-9_]{3,70}$")
ALLOWED_STEMS = {"bass", "drums", "other", "vocals", "guitar", "piano", "instrumental"}
ALLOWED_URL_HOSTS = {"stemsplit.github.io", "huggingface.co"}
ALLOWED_FORMATS = {"ONNX_FP16WEIGHTS", "MLX_FLOAT32_SAFETENSORS"}
ALLOWED_RUNTIME = {"WINDOWS_ONNX_UNVALIDATED", "APPLE_MLX_NOT_WINDOWS"}
ALLOWED_LICENSE = {
    "PUBLISHER_CLAIMS_MIT_REVERIFY_PINNED_ARTIFACT",
    "UNKNOWN_FROM_UPSTREAM_CARD",
    "NO_WEIGHT_SPECIFIC_REDISTRIBUTION_LICENSE_RECORDED",
}
MODEL_FAMILIES = {
    "htdemucs_4s_onnx": "HTDemucs",
    "htdemucs_ft_bass_onnx": "HTDemucs",
    "htdemucs_6s_onnx": "HTDemucs",
    "bs_roformer_sw_mlx": "BS-RoFormer",
    "uvr_mdx_inst_hq3_mlx": "UVR-MDX-Net"
}

MODEL_NOTE_CODES = {
    "htdemucs_4s_onnx": "ONNX_NOT_RAM",
    "htdemucs_ft_bass_onnx": "BASS_SPECIALIST_UNVALIDATED",
    "htdemucs_6s_onnx": "GUITAR_NOT_LEAD_RHYTHM",
    "bs_roformer_sw_mlx": "APPLE_MLX_WEIGHTS_UNKNOWN",
    "uvr_mdx_inst_hq3_mlx": "INSTRUMENTAL_NOT_BASS"
}

MODEL_SOURCE_STEMS = {
    "htdemucs_4s_onnx": [
        "drums",
        "bass",
        "other",
        "vocals"
    ],
    "htdemucs_ft_bass_onnx": [
        "bass"
    ],
    "htdemucs_6s_onnx": [
        "drums",
        "bass",
        "other",
        "vocals",
        "guitar",
        "piano"
    ],
    "bs_roformer_sw_mlx": [
        "bass",
        "drums",
        "other",
        "vocals",
        "guitar",
        "piano"
    ],
    "uvr_mdx_inst_hq3_mlx": [
        "instrumental",
        "vocals"
    ]
}

PUBLIC_EVIDENCE_URLS = {
    "https://stemsplit.github.io/demucs-onnx/models/",
    "https://huggingface.co/ssmall256/mlx-audio-separator",
    "https://huggingface.co/ssmall256/mlx-audio-separator/blob/main/THIRD_PARTY_NOTICES.md",
}

CANDIDATE_KEYS = {
    "model_id", "family", "role", "artifact_format", "published_artifact_size",
    "size_unit", "source_stems", "source_url", "size_source_url",
    "weights_license_source_url", "weight_license_evidence", "runtime_context",
    "note_code", "weights_license_independently_cleared", "local_bundle_sha256_verified",
    "local_ram_peak_measured", "network_isolation_proven", "approved_for_execution",
}


class ModelCardError(ValueError):
    """Invalid or falsely authorized research comparison."""


def _public_https_url(value: Any) -> bool:
    return isinstance(value, str) and value in PUBLIC_EVIDENCE_URLS


def validate_candidate_catalog(payload: Any) -> tuple[dict[str, Any], ...]:
    """Validate every field before even displaying any comparison conclusions."""
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "purpose", "as_of", "candidate_cards"
    } or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ModelCardError("MODEL_CATALOG_SCHEMA_INVALID")
    if payload["purpose"] != "RESEARCH_ONLY_NO_DOWNLOAD_NO_INFERENCE":
        raise ModelCardError("MODEL_CATALOG_EXECUTION_AUTHORITY_FORBIDDEN")
    if not isinstance(payload["as_of"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", payload["as_of"]
    ):
        raise ModelCardError("MODEL_CATALOG_DATE_INVALID")
    cards = payload.get("candidate_cards")
    if not isinstance(cards, list) or not 2 <= len(cards) <= 16:
        raise ModelCardError("MODEL_CARDS_MISSING_OR_TOO_MANY")

    seen: set[str] = set()
    verified = []
    for card in cards:
        if not isinstance(card, dict) or set(card) != CANDIDATE_KEYS:
            raise ModelCardError("MODEL_CARD_FIELDS_INVALID")
        model_id = card["model_id"]
        if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id) or model_id not in MODEL_FAMILIES or model_id in seen:
            raise ModelCardError("MODEL_CARD_IDENTIFIER_INVALID_OR_DUPLICATED")
        seen.add(model_id)
        if card["family"] != MODEL_FAMILIES[model_id]:
            raise ModelCardError("MODEL_FAMILY_INVALID")
        stems = card["source_stems"]
        if (not isinstance(stems, list) or not stems or len(stems) != len(set(map(str, stems)))
                or any(not isinstance(s, str) or s not in ALLOWED_STEMS for s in stems)
                or stems != MODEL_SOURCE_STEMS[model_id]):
            raise ModelCardError("MODEL_STEM_SET_INVALID")
        expected = "BASS_SOURCE_CANDIDATE" if "bass" in stems else "NEGATIVE_CONTROL_NOT_BASS"
        if card["role"] != expected:
            raise ModelCardError("INSTRUMENTAL_MIX_IS_NOT_BASS_STEM")
        if card["artifact_format"] not in ALLOWED_FORMATS or card["size_unit"] not in {"MB", "MiB"}:
            raise ModelCardError("MODEL_ARTIFACT_FORMAT_INVALID")
        size = card["published_artifact_size"]
        if type(size) not in (int, float) or not 1 <= size <= 4096:
            raise ModelCardError("MODEL_PUBLISHED_SIZE_INVALID")
        if any(not _public_https_url(card[key]) for key in (
            "source_url", "size_source_url", "weights_license_source_url"
        )):
            raise ModelCardError("MODEL_PUBLIC_EVIDENCE_URL_INVALID")
        if card["weight_license_evidence"] not in ALLOWED_LICENSE:
            raise ModelCardError("MODEL_WEIGHT_RIGHTS_EVIDENCE_INVALID")
        if card["runtime_context"] not in ALLOWED_RUNTIME or (
            card["artifact_format"].startswith("MLX_")
            != (card["runtime_context"] == "APPLE_MLX_NOT_WINDOWS")
        ):
            raise ModelCardError("MODEL_PLATFORM_CLAIM_INVALID")
        if card["note_code"] != MODEL_NOTE_CODES[model_id]:
            raise ModelCardError("MODEL_CARD_NOTE_INVALID")
        # Nothing in this published evidence admits a local model; these
        # are all independent hard gates and cannot be inferred from a card.
        for field in (
            "weights_license_independently_cleared",
            "local_bundle_sha256_verified",
            "local_ram_peak_measured",
            "network_isolation_proven",
            "approved_for_execution",
        ):
            if card[field] is not False:
                raise ModelCardError("MODEL_CARD_UNPROVEN_PERMISSION")
        verified.append(card)
    if not any(c["role"] == "BASS_SOURCE_CANDIDATE" for c in verified):
        raise ModelCardError("NO_BASS_SOURCE_CANDIDATE")
    if not any(c["role"] == "NEGATIVE_CONTROL_NOT_BASS" for c in verified):
        raise ModelCardError("NO_FALSE_BASS_SOURCE_CONTROL")
    return tuple(verified)


def public_research_comparison(payload: Any) -> dict[str, Any]:
    """No original media, model file path, hash, local host telemetry or execution."""
    cards = validate_candidate_catalog(payload)
    return {
        "status": "RESEARCH_ONLY_NO_EXECUTION",
        "candidate_count": len(cards),
        "bass_stem_candidates": [c["model_id"] for c in cards if c["role"] == "BASS_SOURCE_CANDIDATE"],
        "not_bass_isolation": [c["model_id"] for c in cards if c["role"] == "NEGATIVE_CONTROL_NOT_BASS"],
        "windows_local_runtime_proven": False,
        "weight_redistribution_rights_proven": False,
        "model_execution_authorized": False,
        "song_or_gameplay_validated": False,
    }


def load_candidate_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_candidate_catalog(payload)
    return payload


if __name__ == "__main__":
    print(json.dumps(public_research_comparison(load_candidate_catalog()), sort_keys=True, indent=2))
