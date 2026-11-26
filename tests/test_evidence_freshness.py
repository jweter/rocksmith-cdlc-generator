from __future__ import annotations

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.evidence_freshness import (
    EvidenceBinding,
    is_fresh,
    stale_reasons,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def _binding(**overrides: object) -> EvidenceBinding:
    fields: dict[str, object] = {
        "code_revision": "rev1",
        "model_id": "model-x",
        "audio_sha256": SHA_A,
    }
    fields.update(overrides)
    return EvidenceBinding(**fields)  # type: ignore[arg-type]


def test_identical_bindings_are_fresh() -> None:
    assert stale_reasons(_binding(), _binding()) == ()
    assert is_fresh(_binding(), _binding()) is True


def test_each_single_change_is_named() -> None:
    assert stale_reasons(_binding(), _binding(code_revision="rev2")) == ("CODE_REVISION_CHANGED",)
    assert stale_reasons(_binding(), _binding(model_id="model-y")) == ("MODEL_CHANGED",)
    assert stale_reasons(_binding(), _binding(audio_sha256=SHA_B)) == ("AUDIO_CHANGED",)


def test_several_changes_are_reported_in_a_fixed_order() -> None:
    reasons = stale_reasons(
        _binding(), _binding(audio_sha256=SHA_B, model_id="model-y", code_revision="rev2")
    )

    assert reasons == ("CODE_REVISION_CHANGED", "MODEL_CHANGED", "AUDIO_CHANGED")
    assert is_fresh(_binding(), _binding(code_revision="rev2")) is False


def test_none_on_both_sides_is_fresh_but_on_one_side_is_a_change() -> None:
    bare = _binding(model_id=None, audio_sha256=None)

    assert stale_reasons(bare, bare) == ()
    assert stale_reasons(bare, _binding()) == ("MODEL_CHANGED", "AUDIO_CHANGED")
    assert stale_reasons(_binding(), bare) == ("MODEL_CHANGED", "AUDIO_CHANGED")


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_code_revision_is_never_fresh(blank: str) -> None:
    assert stale_reasons(_binding(code_revision=blank), _binding(code_revision=blank)) == (
        "BINDING_MISSING",
    )


def test_a_blank_model_id_is_never_fresh() -> None:
    assert stale_reasons(_binding(model_id=" "), _binding(model_id=" ")) == ("BINDING_MISSING",)


@pytest.mark.parametrize("bad", ["abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65, ""])
def test_a_malformed_audio_sha_is_never_fresh(bad: str) -> None:
    assert stale_reasons(_binding(audio_sha256=bad), _binding(audio_sha256=bad)) == (
        "BINDING_MISSING",
    )


@pytest.mark.parametrize("missing", [None, "rev1", {"code_revision": "rev1"}, 7])
def test_a_missing_or_wrong_type_binding_is_never_fresh(missing: object) -> None:
    assert stale_reasons(missing, _binding()) == ("BINDING_MISSING",)
    assert stale_reasons(_binding(), missing) == ("BINDING_MISSING",)
    assert stale_reasons(missing, missing) == ("BINDING_MISSING",)
    assert is_fresh(missing, _binding()) is False


def test_binding_is_immutable() -> None:
    binding = _binding()
    with pytest.raises(ValidationError):
        binding.code_revision = "other"  # type: ignore[misc]
