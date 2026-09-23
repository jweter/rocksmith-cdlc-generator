from pathlib import Path


MATRIX = Path(__file__).resolve().parents[1] / "docs" / "eof-subsystem-parity-matrix.md"
ALLOWED_STATUSES = {"UNASSESSED", "PARTIAL", "PARITY", "PARITY+", "DIVERGENT", "GAP", "N/A"}
ALLOWED_REUSE = {"study", "port", "direct", "retain", "port/direct", "study/port", "retain/port"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3", "P4", "P5", "P6"}


def _data_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 7 and cells[0] not in {"Subsystem"}:
            rows.append(cells)
    return rows


def test_every_eof_parity_row_has_explicit_governed_status_and_priority() -> None:
    rows = _data_rows()
    assert rows, "EOF parity matrix must contain subsystem rows"
    for subsystem, reference, area, status, reuse, priority, notes in rows:
        assert subsystem, "subsystem name must not be blank"
        assert reference, f"{subsystem}: reference must not be blank"
        assert area, f"{subsystem}: project area must not be blank"
        assert status in ALLOWED_STATUSES, f"{subsystem}: unknown status {status!r}"
        assert reuse in ALLOWED_REUSE, f"{subsystem}: unknown reuse policy {reuse!r}"
        assert priority in ALLOWED_PRIORITIES, f"{subsystem}: unknown priority {priority!r}"
        assert notes, f"{subsystem}: exit condition/evidence must not be blank"


def test_closed_parity_rows_cannot_lack_evidence_notes() -> None:
    for subsystem, _reference, _area, status, _reuse, _priority, notes in _data_rows():
        if status in {"PARITY", "PARITY+", "DIVERGENT"}:
            assert len(notes) >= 20, f"{subsystem}: closed status requires concrete evidence notes"
