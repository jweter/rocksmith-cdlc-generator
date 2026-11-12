"""The package under test must be this checkout's own source, not another editable install.

On a machine where ``rocksmith-cdlc-generator`` is installed editable from a different checkout, plain ``pytest``
imports that older copy and reports failures the checkout does not have (seen 2026-11-11: five false failures in
``tests/test_rocksmith_xml.py``). Fail loudly and say how to fix it instead.
"""

from __future__ import annotations

from pathlib import Path

import rocksmith_cdlc_generator

CHECKOUT_SRC = Path(__file__).resolve().parents[1] / "src"


def test_the_package_under_test_is_this_checkouts_own_source() -> None:
    imported = Path(rocksmith_cdlc_generator.__file__).resolve()
    assert CHECKOUT_SRC in imported.parents, (
        f"tests imported {imported}, not {CHECKOUT_SRC}. Another editable install shadows this checkout; "
        "run with PYTHONPATH=src (or reinstall this checkout with `pip install -e .`)."
    )
