from pathlib import Path

from rocksmith_cdlc_generator.hashing import sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"rocksmith")
    assert sha256_file(fixture) == "2c44584abc3d96206ef618bf5261350226072720054b74360396cc7a1910b851"
