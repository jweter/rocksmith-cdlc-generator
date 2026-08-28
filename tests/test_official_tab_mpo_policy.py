from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import official_tab_reference


class _FakeImage:
    def __init__(self, image_format: str) -> None:
        self.format = image_format
        self.seek_calls: list[int] = []
        self.verified = False

    def __enter__(self) -> "_FakeImage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def seek(self, frame: int) -> None:
        self.seek_calls.append(frame)

    def verify(self) -> None:
        self.verified = True


def test_jpeg_suffix_accepts_pillow_mpo_container(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "phone-tab.jpeg"
    source.write_bytes(b"fixture bytes are not decoded because Image.open is stubbed")
    opened = _FakeImage("MPO")
    monkeypatch.setattr(official_tab_reference.Image, "open", lambda _path: opened)

    official_tab_reference._verify_supported_image(source)

    assert opened.seek_calls == [0]
    assert opened.verified is True


def test_png_suffix_does_not_accept_mpo_container(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "wrong-container.png"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(
        official_tab_reference.Image,
        "open",
        lambda _path: _FakeImage("MPO"),
    )

    with pytest.raises(ValueError, match="unsupported official TAB image format: MPO"):
        official_tab_reference._verify_supported_image(source)
