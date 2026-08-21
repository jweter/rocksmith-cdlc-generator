"""Regenerate the original, non-commercial GP5 compatibility source fixture."""

from pathlib import Path

import guitarpro
from guitarpro import models


def main() -> None:
    destination = Path(__file__).with_name("synthetic.gp5")
    song = models.Song(title="Synthetic EOF compatibility fixture", tempo=120)
    track = song.tracks[0]
    track.name = "Synthetic Bass"
    track.channel.instrument = 33
    track.strings = [
        models.GuitarString(1, 43),
        models.GuitarString(2, 38),
        models.GuitarString(3, 33),
        models.GuitarString(4, 28),
    ]

    voice = track.measures[0].voices[0]
    first = models.Beat(
        voice,
        duration=models.Duration(value=4),
        start=960,
        status=models.BeatStatus.normal,
    )
    first.notes.append(
        models.Note(
            first,
            value=0,
            string=4,
            type=models.NoteType.normal,
            effect=models.NoteEffect(palmMute=True),
        )
    )
    second = models.Beat(
        voice,
        duration=models.Duration(value=4),
        start=1920,
        status=models.BeatStatus.normal,
    )
    second.notes.append(
        models.Note(
            second,
            value=2,
            string=3,
            type=models.NoteType.normal,
            effect=models.NoteEffect(
                vibrato=True,
                slides=[models.SlideType.shiftSlideTo],
            ),
        )
    )
    voice.beats = [first, second]
    guitarpro.write(song, destination, version=(5, 1, 0))


if __name__ == "__main__":
    main()
