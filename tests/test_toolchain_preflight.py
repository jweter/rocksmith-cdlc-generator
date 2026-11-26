from __future__ import annotations

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.toolchain_preflight import run_toolchain_preflight


def _which(found: dict[str, str]):  # type: ignore[no-untyped-def]
    return lambda name: found.get(name)


def test_all_tools_resolved_is_ready() -> None:
    result = run_toolchain_preflight(["wwise", "psarc"], _which({"wwise": "C:/w", "psarc": "/p"}))

    assert result.status == "READY"
    assert result.reason == ""
    assert result.missing == ()
    assert dict(result.resolved) == {"wwise": "C:/w", "psarc": "/p"}
    assert result.blocked_evidence == ""


def test_a_missing_tool_blocks_and_is_named() -> None:
    result = run_toolchain_preflight(["wwise", "psarc"], _which({"psarc": "/p"}))

    assert result.status == "BLOCKED"
    assert result.reason == "MISSING_TOOLS"
    assert result.missing == ("wwise",)
    assert "wwise" in result.blocked_evidence
    assert dict(result.resolved) == {"psarc": "/p"}


def test_missing_tools_are_listed_sorted() -> None:
    result = run_toolchain_preflight(["zeta", "alpha", "mid"], _which({}))

    assert result.status == "BLOCKED"
    assert result.missing == ("alpha", "mid", "zeta")


def test_an_empty_requirement_list_is_blocked_never_a_vacuous_pass() -> None:
    result = run_toolchain_preflight([], _which({}))

    assert result.status == "BLOCKED"
    assert result.reason == "NO_TOOLS_DECLARED"
    assert result.blocked_evidence


def test_duplicate_names_are_resolved_once() -> None:
    calls: list[str] = []

    def which(name: str) -> str | None:
        calls.append(name)
        return "/x"

    result = run_toolchain_preflight(["tool", "tool", "tool"], which)

    assert result.status == "READY"
    assert calls == ["tool"]
    assert result.resolved == (("tool", "/x"),)


@pytest.mark.parametrize("bad", ["", " ", " padded", "padded ", "two words", None, 5, b"tool"])
def test_invalid_tool_names_block_without_calling_which(bad: object) -> None:
    def which(name: str) -> str | None:
        raise AssertionError("must not look up an invalid name")

    result = run_toolchain_preflight(["ok", bad], which)

    assert result.status == "BLOCKED"
    assert result.reason == "INVALID_TOOL_NAME"


def test_a_lookup_that_raises_counts_as_missing() -> None:
    def which(name: str) -> str | None:
        if name == "boom":
            raise RuntimeError("lookup failed")
        return "/ok"

    result = run_toolchain_preflight(["ok", "boom"], which)

    assert result.status == "BLOCKED"
    assert result.missing == ("boom",)


@pytest.mark.parametrize("returned", [None, "", "   ", 0, b"path", ["x"]])
def test_a_non_path_lookup_result_counts_as_missing(returned: object) -> None:
    result = run_toolchain_preflight(["tool"], lambda _name: returned)  # type: ignore[arg-type,return-value]

    assert result.status == "BLOCKED"
    assert result.missing == ("tool",)


def test_result_is_immutable() -> None:
    result = run_toolchain_preflight(["t"], _which({"t": "/t"}))
    with pytest.raises(ValidationError):
        result.status = "BLOCKED"  # type: ignore[misc]
