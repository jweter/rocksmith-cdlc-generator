from rocksmith_cdlc_generator.tone_manifest_parser import parse_tone_manifest_payload


def _manifest(*, arrangement_name="Lead", props=None, tones=None):
    return {
        "ModelName": "RSEnumerable_Song",
        "Entries": {
            "song-id": {
                "arrangement-id": {
                    "ArtistName": "Synthetic Artist",
                    "SongName": "Synthetic Song",
                    "ArrangementName": arrangement_name,
                    "ArrangementProperties": props or {"PathLead": 1, "PathRhythm": 0, "PathBass": 0},
                    "Tone_Base": "Synthetic Base",
                    "Tones": tones if tones is not None else [
                        {
                            "Key": "synthetic-tone",
                            "Name": "Synthetic Base",
                            "ToneDescriptors": ["distortion", "delay"],
                            "GearList": {
                                "Amp": {"Key": "amp-synthetic", "KnobValues": {"Gain": 0.7}},
                                "Cabinet": {"Key": "cab-synthetic", "KnobValues": {}},
                                "PrePedal1": {"Key": "drive-synthetic", "KnobValues": {"Drive": 0.4}},
                                "Rack1": {"Key": "delay-synthetic", "KnobValues": {"Time": 0.35}},
                            },
                        }
                    ],
                }
            }
        },
    }


def _parse(payload):
    return parse_tone_manifest_payload(
        payload,
        source_psarc_sha256="a" * 64,
        source_path="private/source.psarc",
        source_type="official_rocksmith",
    )


def test_parses_supported_manifest_tone_and_knobs() -> None:
    records = _parse(_manifest())
    assert len(records) == 1
    tone = records[0]
    assert tone.artist == "Synthetic Artist"
    assert tone.title == "Synthetic Song"
    assert tone.arrangement == "lead"
    assert tone.tone_key == "synthetic-tone"
    assert tone.tone_descriptors == ["distortion", "delay"]
    assert [(item.slot, item.device_key) for item in tone.components] == [
        ("Amp", "amp-synthetic"),
        ("Cabinet", "cab-synthetic"),
        ("PrePedal1", "drive-synthetic"),
        ("Rack1", "delay-synthetic"),
    ]
    assert tone.components[0].knob_values == {"Gain": 0.7}
    assert tone.tone_changes == []


def test_arrangement_properties_take_priority_over_name() -> None:
    records = _parse(_manifest(arrangement_name="Combo", props={"PathLead": 0, "PathRhythm": 0, "PathBass": 1}))
    assert records[0].arrangement == "bass"


def test_vocals_are_ignored() -> None:
    assert _parse(_manifest(arrangement_name="Vocals")) == []


def test_unsupported_arrangement_is_ignored() -> None:
    payload = _manifest(arrangement_name="Combo", props={"PathLead": 0, "PathRhythm": 0, "PathBass": 0})
    assert _parse(payload) == []


def test_missing_or_malformed_tone_data_is_not_invented() -> None:
    payload = _manifest(tones=[
        {"Name": "No key", "GearList": {"Amp": {"Key": "amp"}}},
        {"Key": "no-gear", "Name": "No gear", "GearList": {}},
        {"Key": "bad-device", "Name": "Bad", "GearList": {"Amp": {"KnobValues": {"Gain": 1}}}},
    ])
    assert _parse(payload) == []


def test_unknown_json_shape_is_ignored() -> None:
    assert _parse({"Entries": ["not-a-manifest"]}) == []
    assert _parse({"something": "else"}) == []


def test_non_numeric_knobs_are_ignored_without_dropping_device() -> None:
    payload = _manifest()
    tone = payload["Entries"]["song-id"]["arrangement-id"]["Tones"][0]
    tone["GearList"]["Amp"]["KnobValues"] = {"Gain": "0.7", "Enabled": True, "Level": 0.5}
    record = _parse(payload)[0]
    assert record.components[0].knob_values == {"Level": 0.5}
