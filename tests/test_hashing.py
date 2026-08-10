from pathlib import Path

from rocksmith_cdlc_generator.hashing import sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"rocksmith")
    assert sha256_file(fixture) == "1efb4baeb8a99e0d598e9ff6c9ceae055f9a0cdd632c15ad48f0dbbdb62a1cde"
