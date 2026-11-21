"""Cached model bundle proof: validate declared bytes, never execute a model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.model_bundle_manifest import inspect_cached_model_bundle


@pytest.fixture
def bundle(tmp_path: Path):
    cache = tmp_path / "cached-models"
    cache.mkdir()
    model = cache / "bass.onnx"
    model.write_bytes(b"synthetic-model-weights-NOT-real-inference")
    config_dir = cache / "config"
    config_dir.mkdir()
    config = config_dir / "bass.yaml"
    config.write_bytes(b"synthetic-config-only")
    manifest = cache / "manifest.json"
    data = {
        "schema_version": 1,
        "model_filename": model.name,
        "files": [
            {"path": model.name, "sha256": sha256_file(model),
             "size_bytes": model.stat().st_size},
            {"path": "config/bass.yaml", "sha256": sha256_file(config),
             "size_bytes": config.stat().st_size},
        ],
    }
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return cache, manifest, model, config, data


def _check(bundle, *, manifest=None):
    cache, default, model, config, data = bundle
    return inspect_cached_model_bundle(
        cache, default if manifest is None else manifest,
        model_filename=model.name, expected_model_sha256=sha256_file(model),
    )


def test_two_files_hash_bound_but_closure_and_license_not_proven(bundle):
    cache, manifest, model, config, data = bundle
    result = _check(bundle)
    assert result.status == "VERIFIED_DECLARED_FILES"
    assert result.manifest_sha256 == sha256_file(manifest)
    assert result.verified_file_count == 2
    assert result.model_sha256 == sha256_file(model)
    assert result.dependency_closure_proven is False
    assert result.license_verified is False
    assert result.network_isolation_proven is False


@pytest.mark.parametrize("changed_path", ["config", "model", "manifest"])
def test_any_declared_file_or_manifest_mutation_invalidates_cached_bundle(bundle, changed_path):
    cache, manifest, model, config, data = bundle
    assert _check(bundle).status == "VERIFIED_DECLARED_FILES"
    if changed_path == "config":
        config.write_bytes(b"other-model-configuration")
    elif changed_path == "model":
        model.write_bytes(b"modelfile-changed")
    else:
        data["model_filename"] = "another-model.onnx"
        manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).status == "BLOCKED"


@pytest.mark.parametrize("dangerous", [
    "../outside.onnx", "./config/bass.yaml", "/absolute/file", "C:/windows/x",
    "config\\bass.yaml", "config//bass.yaml", ".hidden", "config/../bass.onnx",
])
def test_manifest_path_traversal_and_ambiguous_paths_fail_closed(bundle, dangerous):
    cache, manifest, model, config, data = bundle
    data["files"][1]["path"] = dangerous
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_PATH_INVALID"


def test_missing_or_duplicate_declared_dependency_fails(bundle):
    cache, manifest, model, config, data = bundle
    config.unlink()
    assert _check(bundle).code == "MODEL_MANIFEST_CONTENT_MISMATCH"
    data["files"][1] = data["files"][0]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_DUPLICATE_PATH"


def test_unlisted_primary_model_is_not_a_complete_bundle(bundle):
    cache, manifest, model, config, data = bundle
    data["files"] = [data["files"][1]]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_PRIMARY_MODEL_MISSING"


def test_manifest_outside_cache_and_symlink_fail_closed(bundle, tmp_path: Path):
    cache, manifest, model, config, data = bundle
    off_cache = tmp_path / "off-cache.json"
    off_cache.write_bytes(manifest.read_bytes())
    assert _check(bundle, manifest=off_cache).code == "MODEL_MANIFEST_OUTSIDE_CACHE"
    link = cache / "linked.json"
    try:
        link.symlink_to(manifest)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unsupported on this Windows test runner")
    assert _check(bundle, manifest=link).code == "MODEL_MANIFEST_SYMLINK"


def test_wrong_length_hash_and_bogus_entry_fail_closed(bundle):
    cache, manifest, model, config, data = bundle
    data["files"][1]["size_bytes"] += 1
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_CONTENT_MISMATCH"
    data["files"][1]["sha256"] = "f" * 64
    data["files"][1]["size_bytes"] -= 1
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_CONTENT_MISMATCH"
    data["files"][1]["sha256"] = "bad"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _check(bundle).code == "MODEL_MANIFEST_ENTRY_INVALID"


def test_manifest_missing_explicit_path_is_blocked(bundle):
    cache, manifest, model, config, data = bundle
    result = inspect_cached_model_bundle(
        cache, None, model_filename=model.name,
        expected_model_sha256=sha256_file(model),
    )
    assert result.code == "MODEL_MANIFEST_REQUIRED"


def test_manifest_and_auxiliary_replaced_mid_scan_cannot_receive_new_digest(
    bundle, monkeypatch
) -> None:
    import rocksmith_cdlc_generator.model_bundle_manifest as module

    cache, manifest, model, config, data = bundle
    original_sha = module.sha256_file
    saw_config = False

    def mutating_hash(path):
        nonlocal saw_config
        digest = original_sha(path)
        if Path(path) == config and not saw_config:
            saw_config = True
            config.write_bytes(b"replacement-configuration-after-initial-check")
            data["files"][1]["sha256"] = original_sha(config)
            data["files"][1]["size_bytes"] = config.stat().st_size
            manifest.write_text(json.dumps(data), encoding="utf-8")
        return digest

    monkeypatch.setattr(module, "sha256_file", mutating_hash)
    result = _check(bundle)
    assert saw_config
    assert result.status == "BLOCKED"
    assert result.code == "MODEL_MANIFEST_CHANGED_DURING_SCAN"
