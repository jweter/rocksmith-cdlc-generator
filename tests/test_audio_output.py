from __future__ import annotations

from types import SimpleNamespace
import sys

from rocksmith_cdlc_generator.audio_output import (
    AudioOutputDevice,
    list_output_devices,
    load_output_preference,
    preferred_output_device,
    select_output_device,
)


class _FakeSoundDevice:
    def __init__(self, devices, *, default_input: int = 0, default_output: int = 1) -> None:
        self._devices = devices
        self.default = SimpleNamespace(device=(default_input, default_output))

    def query_devices(self):
        return self._devices


def _devices():
    return [
        {"name": "Microphone only", "max_output_channels": 0, "default_samplerate": 48000.0},
        {"name": "Speakers", "max_output_channels": 2, "default_samplerate": 48000.0},
        {"name": "USB Interface", "max_output_channels": 4, "default_samplerate": 44100.0},
    ]


def test_list_output_devices_filters_inputs_and_marks_default(monkeypatch) -> None:
    fake = _FakeSoundDevice(_devices(), default_output=2)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)

    devices = list_output_devices()

    assert [(device.index, device.name) for device in devices] == [
        (1, "Speakers"),
        (2, "USB Interface"),
    ]
    assert [device.is_default for device in devices] == [False, True]
    assert devices[1].default_samplerate == 44100.0


def test_selected_output_persists_and_survives_index_reordering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fake = _FakeSoundDevice(_devices(), default_input=7, default_output=1)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    chosen = AudioOutputDevice(
        index=2,
        name="USB Interface",
        max_output_channels=4,
        default_samplerate=44100.0,
    )

    select_output_device(chosen)

    assert fake.default.device == (7, 2)
    assert load_output_preference() == (2, "USB Interface")

    reordered = [
        AudioOutputDevice(3, "USB Interface", 4, 44100.0),
        AudioOutputDevice(1, "Speakers", 2, 48000.0, is_default=True),
    ]
    assert preferred_output_device(reordered) == reordered[0]


def test_nonpersistent_selection_changes_runtime_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fake = _FakeSoundDevice(_devices(), default_input=4, default_output=1)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    selected = AudioOutputDevice(2, "USB Interface", 4, 44100.0)

    select_output_device(selected, persist=False)

    assert fake.default.device == (4, 2)
    assert load_output_preference() == (None, None)
