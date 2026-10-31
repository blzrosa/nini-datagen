"""Benchmark contra o MVP (fora da suíte padrão): ``uv run pytest -m bench -s``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pl = pytest.importorskip("polars")
if getattr(pl, "IS_FAKE", False):
    pytest.skip("precisa do Polars de verdade", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
bench = importlib.import_module("bench")

pytestmark = pytest.mark.bench


@pytest.mark.parametrize("case", [c for c in bench.CASES if c.name in bench.MVP], ids=lambda c: c.name)
def test_not_slower_than_mvp(case):
    ns = bench.measure(case, 5_000_000, 1)
    ref = bench.MVP[case.name][0]
    print(f"\n{case.name}: {ns:.2f} ns/linha (MVP {ref:.1f})")
    assert ns <= ref * bench.TOLERANCE, f"{case.name}: {ns:.2f} ns/linha, MVP {ref:.1f}"
